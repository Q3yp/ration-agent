import numpy as np
from scipy.optimize import minimize
from typing import Callable, Dict, List, Any, Optional, Tuple
from functools import lru_cache
import json
import logging
import math

logger = logging.getLogger(__name__)

# Profiling counters for cache performance monitoring
class NASEMCacheStats:
    """Track NASEM cache hit/miss statistics."""
    hits: int = 0
    misses: int = 0
    
    @classmethod
    def reset(cls):
        cls.hits = 0
        cls.misses = 0
    
    @classmethod
    def hit(cls):
        cls.hits += 1
    
    @classmethod
    def miss(cls):
        cls.misses += 1
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        total = cls.hits + cls.misses
        return {
            "cache_hits": cls.hits,
            "cache_misses": cls.misses,
            "total_lookups": total,
            "hit_rate": cls.hits / max(total, 1) * 100
        }


def _make_cache_key(feed_percentages: np.ndarray) -> Tuple[float, ...]:
    """Create a hashable cache key from feed percentages.
    
    Uses exact values (no rounding) to ensure cache hits ONLY for identical
    compositions within the same optimizer iteration. This preserves gradient
    accuracy across iterations while consolidating multiple constraint 
    evaluations within a single iteration.
    """
    return tuple(float(x) for x in feed_percentages)


def calculate_predicted_dmi_lact2(
    feed_percentages: np.ndarray,
    feeds: Dict[str, Dict],
    selected_feeds: List[str],
    milk_prod: float
) -> float:
    """
    Calculate DMI from diet composition using NASEM equation 9 (Lact2).
    
    DMI = 12.0 - 0.107*ForageNDF + 8.17*(ADF/NDF) + 0.0253*ForDNDF48 
          - 0.328*(ADF/NDF - 0.602)*(ForDNDF48 - 48.3) 
          + 0.225*MilkProd + 0.00390*(ForDNDF48 - 48.3)*(MilkProd - 33.1)
    
    Args:
        feed_percentages: Array of feed inclusion percentages (sum to 100)
        feeds: Feed database with nutrient compositions
        selected_feeds: List of feed names in same order as percentages
        milk_prod: Target milk production in kg/day
        
    Returns:
        Predicted DMI in kg/day
    """
    # Calculate diet composition from feed mix
    dt_ndf = 0.0
    dt_adf = 0.0
    dt_for_ndf = 0.0
    dt_for_dndf48 = 0.0
    
    for i, feed_name in enumerate(selected_feeds):
        pct = feed_percentages[i]
        nutrients = feeds[feed_name].get("nutrients", {})
        
        fd_ndf = nutrients.get("Fd_NDF", 0.0)
        fd_adf = nutrients.get("Fd_ADF", 0.0)
        fd_conc = nutrients.get("Fd_Conc", 0.0)  # 0=forage, 100=concentrate
        fd_dndf48 = nutrients.get("Fd_DNDF48_NDF", 48.0)  # Default to 48%
        
        dt_ndf += pct * fd_ndf / 100
        dt_adf += pct * fd_adf / 100
        
        # Forage NDF (only count NDF from forages)
        if fd_conc < 50:  # Forage
            fd_for_ndf = fd_ndf
            dt_for_ndf += pct * fd_for_ndf / 100
            dt_for_dndf48 += pct * fd_ndf * fd_dndf48 / 10000  # Weighted by NDF content
    
    # Calculate ForDNDF48 as % of ForNDF
    if dt_for_ndf > 0:
        dt_for_dndf48_forndf = dt_for_dndf48 / dt_for_ndf * 100
    else:
        dt_for_dndf48_forndf = 48.0  # Default
    
    # Calculate ADF/NDF ratio
    if dt_ndf > 0:
        adf_ndf_ratio = dt_adf / dt_ndf
    else:
        adf_ndf_ratio = 0.6  # Default
    
    # NASEM Equation 9
    dmi = (12.0 
           - 0.107 * dt_for_ndf 
           + 8.17 * adf_ndf_ratio 
           + 0.0253 * dt_for_dndf48_forndf
           - 0.328 * (adf_ndf_ratio - 0.602) * (dt_for_dndf48_forndf - 48.3)
           + 0.225 * milk_prod 
           + 0.00390 * (dt_for_dndf48_forndf - 48.3) * (milk_prod - 33.1))
    
    return max(dmi, 10.0)  # Minimum 10 kg DMI for safety



class FormulationOptimizer:
    """
    Feed formulation optimizer using SLSQP (Sequential Least Squares Programming).
    
    Supports:
    - concentration: nutrient % of dry matter
    - daily_total: absolute daily nutrient intake (including mp, me, dmi)
    - daily_total with mp_balance/me_balance: balance-based constraints
      where tolerance is expressed as % of NASEM-computed requirement
    - ratio: ratios between nutrients
    - inclusion: feed inclusion limits
    
    For dairy cows, can:
    - Predict DMI from diet composition using NASEM equation 9
    - Calculate MP supply from diet for MP constraints (g/day)
    - Calculate ME supply from diet for ME constraints (Mcal/day)
    - Compute MP/ME balance (supply - requirement) for balance constraints
    """
    
    def __init__(self):
        self.feeds = {}
        self.constraints = []
        self.optimization_goal = "minimize_cost"
        self.animal_params = None
        self.dmi_override = None  # Optional DMI override value
        # Cache for NASEM values - keyed by rounded feed percentages
        # Dramatically reduces redundant NASEM calls during optimization
        self._nasem_cache: Dict[Tuple[float, ...], Dict[str, float]] = {}
    
    def set_feeds(self, feeds: Dict[str, Dict[str, Any]]):
        """Set available feeds with their nutrient composition and costs."""
        self.feeds = feeds
    
    def set_animal_params(
        self,
        body_weight: float = 650.0,
        dim: int = 90,
        parity: int = 2,
        milk_prod: float = 35.0,
        bcs: float = 3.0,
        milk_fat_pct: float = 3.5,
        milk_protein_pct: float = 3.2,
        milk_price_per_kg: float = 3.0
    ):
        """
        Set animal parameters for DMI/MP prediction.
        
        Args:
            body_weight: Body weight in kg
            dim: Days in milk
            parity: Number of lactations
            milk_prod: Target milk production kg/day
            bcs: Body condition score (1-5)
            milk_fat_pct: Milk fat percentage
            milk_protein_pct: Milk protein percentage
            milk_price_per_kg: Milk price per kg (default 3.0, used for maximize_profit)
        """
        # Calculate NE milk output for equation 8
        milk_lac_pct = 4.85  # Default lactose
        ne_milk_per_kg = 0.0929 * milk_fat_pct + 0.0547 * milk_protein_pct + 0.0395 * milk_lac_pct
        ne_milk_out = ne_milk_per_kg * milk_prod
        
        self.animal_params = {
            "body_weight": body_weight,
            "dim": dim,
            "parity": parity,
            "milk_prod": milk_prod,
            "bcs": bcs,
            "ne_milk_out": ne_milk_out,
            "milk_price_per_kg": milk_price_per_kg
        }
    
    def set_dmi_override(self, dmi_kg: float):
        """Set a fixed DMI value instead of predicting from diet."""
        self.dmi_override = dmi_kg
    
    def _get_dmi(self, feed_percentages: np.ndarray, selected_feeds: List[str]) -> float:
        """Get DMI - either override or predicted from diet."""
        if self.dmi_override is not None:
            return self.dmi_override
        elif self.animal_params is not None:
            return calculate_predicted_dmi_lact2(
                feed_percentages, self.feeds, selected_feeds, 
                self.animal_params["milk_prod"]
            )
        else:
            return 25.0  # Default fallback
    
    def _build_diet_for_nasem(
        self, 
        feed_percentages: np.ndarray, 
        selected_feeds: List[str],
        dmi_kg: float
    ) -> Dict[str, float]:
        """Convert feed percentages to NASEM diet composition format.
        
        Args:
            feed_percentages: Array of feed inclusion percentages (sum to 100)
            selected_feeds: List of feed names in same order as percentages
            dmi_kg: Total dry matter intake in kg/day
            
        Returns:
            Dict of {feed_key: kg_dm_per_day}
        """
        diet = {}
        for i, feed_name in enumerate(selected_feeds):
            pct = feed_percentages[i]
            if pct > 0:
                diet[feed_name] = dmi_kg * (pct / 100)
        return diet
    
    def _get_nasem_values(
        self, 
        feed_percentages: np.ndarray, 
        selected_feeds: List[str],
        param_names: List[str]
    ) -> Dict[str, float]:
        """Calculate multiple NASEM values in a single model run with caching.
        
        Uses per-iteration caching: when the same feed_percentages are encountered
        (within rounding tolerance), returns cached values. This consolidates
        multiple constraint evaluations into a single NASEM call per iteration.
        
        Args:
            feed_percentages: Feed percentages array
            selected_feeds: List of feed names
            param_names: List of NASEM parameter names to extract, e.g.:
                        ["An_MPIn_g", "An_MEIn"]
        
        Returns:
            Dict of {param_name: value}. Missing/error values are 0.0
        """
        result = {name: 0.0 for name in param_names}
        
        if self.animal_params is None:
            return result
        
        # Create cache key from exact feed percentages
        # No rounding = cache hits ONLY for identical x within same iteration
        cache_key = _make_cache_key(feed_percentages)
        
        # Check if we have cached values for this composition
        if cache_key in self._nasem_cache:
            cached = self._nasem_cache[cache_key]
            NASEMCacheStats.hit()
            # Extract requested values from cache
            for name in param_names:
                if name in cached:
                    result[name] = cached[name]
            return result
        
        # Cache miss - call NASEM with ALL commonly needed params
        # This ensures subsequent calls for other params can use the cache
        NASEMCacheStats.miss()
        
        # Request all params we might need during optimization
        all_params = [
            "An_MPIn_g",          # MP supply
            "An_MEIn",            # ME supply  
            "An_MPuse_g_Trg",     # MP requirement (for balance)
            "An_MEuse",           # ME requirement (for balance)
            "Mlk_Prod_MPalow",    # MP-allowable milk
            "Mlk_Prod_NEalow",    # NE-allowable milk
        ]
        
        try:
            from services.nasem_service import get_nasem_service
            nasem_service = get_nasem_service()
            
            dmi = self._get_dmi(feed_percentages, selected_feeds)
            diet = self._build_diet_for_nasem(feed_percentages, selected_feeds, dmi)
            
            # Build animal input from our params
            animal_input = nasem_service.build_animal_input(
                body_weight_kg=self.animal_params.get("body_weight", 650.0),
                days_in_milk=self.animal_params.get("dim", 90),
                parity=self.animal_params.get("parity", 2),
                target_milk_kg=self.animal_params.get("milk_prod", 35.0),
                target_dmi_kg=dmi,
                bcs=self.animal_params.get("bcs", 3.0)
            )
            
            # Call NASEM once for ALL values
            full_result = nasem_service.calculate_values(
                self.feeds, diet, animal_input, all_params
            )
            
            # Cache the full result for future lookups
            self._nasem_cache[cache_key] = full_result
            
            # Return only the requested values
            for name in param_names:
                if name in full_result:
                    result[name] = full_result[name]
            
            return result
            
        except Exception as e:
            logger.warning(f"NASEM calculation failed: {e}")
            return result
    
    # Convenience methods for single-value constraints
    def _get_nasem_mp_balance(
        self, feed_percentages: np.ndarray, selected_feeds: List[str]
    ) -> Tuple[float, float, float]:
        """Get MP supply, requirement, and balance from NASEM.
        
        Returns:
            (supply_g, requirement_g, balance_g) where balance = supply - requirement
        """
        result = self._get_nasem_values(
            feed_percentages, selected_feeds,
            ["An_MPIn_g", "An_MPuse_g_Trg"]
        )
        supply = result.get("An_MPIn_g", 0.0)
        requirement = result.get("An_MPuse_g_Trg", 0.0)
        return supply, requirement, supply - requirement

    def _get_nasem_me_balance(
        self, feed_percentages: np.ndarray, selected_feeds: List[str]
    ) -> Tuple[float, float, float]:
        """Get ME supply, requirement, and balance from NASEM.
        
        Returns:
            (supply_mcal, requirement_mcal, balance_mcal)
        """
        result = self._get_nasem_values(
            feed_percentages, selected_feeds,
            ["An_MEIn", "An_MEuse"]
        )
        supply = result.get("An_MEIn", 0.0)
        requirement = result.get("An_MEuse", 0.0)
        return supply, requirement, supply - requirement

    def _get_nasem_milk_prod(self, feed_percentages: np.ndarray, selected_feeds: List[str]) -> float:
        """Get predicted milk production using least-constraint approach.
        
        Returns min(Mlk_Prod_MPalow, Mlk_Prod_NEalow) - the milk limited by
        whichever nutrient (MP or NE) is most limiting.
        
        Returns:
            Predicted milk production in kg/day
        """
        result = self._get_nasem_values(
            feed_percentages, selected_feeds, 
            ["Mlk_Prod_MPalow", "Mlk_Prod_NEalow"]
        )
        mp_milk = result.get("Mlk_Prod_MPalow", 0.0)
        ne_milk = result.get("Mlk_Prod_NEalow", 0.0)
        
        # Use minimum of MP-allowable and NE-allowable (least constraint)
        # If either is 0 or missing, use the other
        if mp_milk <= 0:
            return ne_milk
        if ne_milk <= 0:
            return mp_milk
        return min(mp_milk, ne_milk)

    def _build_objective(
        self,
        selected_feeds: List[str],
        optimization_goal: str
    ) -> Callable[[np.ndarray], float]:
        """Build the base objective used by the optimizer."""
        if optimization_goal == "feasibility":
            def objective(x: np.ndarray) -> float:
                return 0.0
            return objective

        if optimization_goal == "maximize_profit":
            milk_price = self.animal_params.get("milk_price_per_kg", 3.0) if self.animal_params else 3.0

            def objective(x: np.ndarray) -> float:
                dmi = self._get_dmi(x, selected_feeds)
                total_feed_cost = self._calculate_feed_cost_per_day(x, selected_feeds, dmi)
                predicted_milk = self._get_nasem_milk_prod(x, selected_feeds)
                milk_revenue = predicted_milk * milk_price
                profit = milk_revenue - total_feed_cost
                return -profit

            return objective

        def objective(x: np.ndarray) -> float:
            return self._calculate_cost_per_kg_dm(x, selected_feeds)

        return objective

    def _calculate_cost_per_kg_dm(
        self,
        feed_percentages: np.ndarray,
        selected_feeds: List[str]
    ) -> float:
        """Calculate ration cost per kg DM."""
        total_cost = 0.0
        for i, feed_name in enumerate(selected_feeds):
            feed_data = self.feeds[feed_name]
            cost_per_kg_dm = feed_data.get("cost_per_kg", 0) / (feed_data.get("dm_percent", 100) / 100)
            total_cost += feed_percentages[i] * cost_per_kg_dm / 100
        return total_cost

    def _calculate_feed_cost_per_day(
        self,
        feed_percentages: np.ndarray,
        selected_feeds: List[str],
        dmi: Optional[float] = None
    ) -> float:
        """Calculate total daily feed cost for the ration."""
        dmi = dmi if dmi is not None else self._get_dmi(feed_percentages, selected_feeds)
        total_feed_cost = 0.0
        for i, feed_name in enumerate(selected_feeds):
            feed_data = self.feeds[feed_name]
            dm_pct = feed_data.get("dm_percent", 100)
            cost_per_kg_dm = feed_data.get("cost_per_kg", 0) / (dm_pct / 100)
            kg_dm = dmi * feed_percentages[i] / 100
            total_feed_cost += kg_dm * cost_per_kg_dm
        return total_feed_cost

    def _default_penalty_weight(self, constraint: Dict[str, Any]) -> float:
        """Default penalty weight used by the compromise fallback."""
        explicit_weight = constraint.get("penalty_weight")
        if explicit_weight is not None:
            try:
                return float(explicit_weight)
            except (TypeError, ValueError):
                logger.warning(f"Invalid penalty_weight ignored: {explicit_weight}")

        priority = str(constraint.get("penalty_priority", "")).strip().lower()
        priority_map = {
            "critical": 1000.0,
            "high": 300.0,
            "medium": 100.0,
            "low": 30.0,
        }
        if priority in priority_map:
            return priority_map[priority]
        return 1.0

    def _constraint_label(self, constraint: Dict[str, Any]) -> str:
        """Human-readable label for diagnostics."""
        c_type = constraint.get("type", "")
        if c_type == "concentration":
            return f"concentration:{constraint.get('nutrient', 'unknown')}"
        if c_type == "daily_total":
            return f"daily_total:{constraint.get('attribute', 'unknown')}"
        if c_type == "ratio":
            numerator = constraint.get("numerator", "unknown")
            denominator = constraint.get("denominator", "unknown")
            return f"ratio:{numerator}/{denominator}"
        return c_type or "unknown"

    def _constraint_scale(
        self,
        constraint: Dict[str, Any],
        min_allowed: Optional[float],
        max_allowed: Optional[float],
        target: Optional[float]
    ) -> float:
        """Normalization scale for penalty calculations."""
        explicit_scale = constraint.get("penalty_scale")
        if explicit_scale is not None:
            try:
                explicit_scale = float(explicit_scale)
                if explicit_scale > 0:
                    return explicit_scale
            except (TypeError, ValueError):
                logger.warning(f"Invalid penalty_scale ignored: {explicit_scale}")

        candidates = [abs(value) for value in (target, min_allowed, max_allowed) if value is not None]
        return max(candidates + [1.0])

    def _constraint_tolerance(self, penalty_scale: float) -> float:
        """Numerical tolerance for classifying a constraint as satisfied."""
        return max(1e-6, penalty_scale * 1e-6)

    def _to_python_scalar(self, value: Any) -> Any:
        """Convert NumPy scalars to plain Python values for cleaner JSON output."""
        if isinstance(value, np.generic):
            return value.item()
        return value

    def _sanitize_constraint_detail(self, detail: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize constraint diagnostics to plain Python types."""
        sanitized = {}
        for key, value in detail.items():
            native_value = self._to_python_scalar(value)
            if isinstance(native_value, float) and math.isfinite(native_value):
                sanitized[key] = round(native_value, 6)
            else:
                sanitized[key] = native_value
        return sanitized

    def _evaluate_constraint(
        self,
        feed_percentages: np.ndarray,
        selected_feeds: List[str],
        constraint: Dict[str, Any],
        index: int
    ) -> Dict[str, Any]:
        """Evaluate one nutritional constraint against a ration."""
        c_type = constraint.get("type", "")
        label = self._constraint_label(constraint)
        penalty_weight = self._default_penalty_weight(constraint)

        detail: Dict[str, Any] = {
            "constraint_index": index,
            "constraint_label": label,
            "type": c_type,
            "actual": None,
            "target": None,
            "min_allowed": None,
            "max_allowed": None,
            "tolerance_percent": constraint.get("tolerance_percent"),
            "unit": "",
            "satisfied": True,
            "violation_direction": None,
            "violation_amount": 0.0,
            "normalized_violation": 0.0,
            "severity_percent": 0.0,
            "penalty_weight": penalty_weight,
            "penalty_scale": 1.0,
            "penalty": 0.0,
            "penalty_applicable": True,
        }

        if c_type == "concentration":
            nutrient = constraint["nutrient"]
            actual = sum(
                feed_percentages[i] * self.feeds[f]["nutrients"].get(nutrient, 0)
                for i, f in enumerate(selected_feeds)
            ) / 100
            detail.update({
                "nutrient": nutrient,
                "actual": actual,
                "min_allowed": constraint.get("min"),
                "max_allowed": constraint.get("max"),
                "unit": "% DM",
            })

        elif c_type == "daily_total":
            attribute = constraint.get("attribute")
            target = constraint.get("target")
            tolerance_pct = float(constraint.get("tolerance_percent", 3.0))
            detail.update({
                "attribute": attribute,
                "target": target,
                "tolerance_percent": tolerance_pct,
            })

            if attribute in ("dmi", "Fd_DM") and self.dmi_override is not None:
                actual_dmi = self._get_dmi(feed_percentages, selected_feeds)
                detail.update({
                    "actual": actual_dmi,
                    "min_allowed": target,
                    "max_allowed": target,
                    "unit": "kg/day",
                    "penalty_applicable": False,
                    "note": "Handled as a DMI override during strict optimization.",
                })
                return self._sanitize_constraint_detail(detail)

            # --- Balance-based constraints (mp_balance, me_balance) ---
            if attribute == "mp_balance":
                supply, requirement, balance = self._get_nasem_mp_balance(
                    feed_percentages, selected_feeds
                )
                tol_min = float(constraint.get("tolerance_min_pct", -tolerance_pct))
                tol_max = float(constraint.get("tolerance_max_pct", tolerance_pct))
                min_allowed = tol_min / 100 * requirement  # e.g. -5% of req
                max_allowed = tol_max / 100 * requirement  # e.g. +5% of req
                detail.update({
                    "actual": balance,
                    "target": 0.0,
                    "min_allowed": min_allowed,
                    "max_allowed": max_allowed,
                    "tolerance_min_pct": tol_min,
                    "tolerance_max_pct": tol_max,
                    "supply": supply,
                    "requirement": requirement,
                    "supply_pct_of_req": round(
                        supply / requirement * 100, 1
                    ) if requirement > 0 else None,
                    "unit": "g/day (balance)",
                })
            elif attribute == "me_balance":
                supply, requirement, balance = self._get_nasem_me_balance(
                    feed_percentages, selected_feeds
                )
                tol_min = float(constraint.get("tolerance_min_pct", -tolerance_pct))
                tol_max = float(constraint.get("tolerance_max_pct", tolerance_pct))
                min_allowed = tol_min / 100 * requirement
                max_allowed = tol_max / 100 * requirement
                detail.update({
                    "actual": balance,
                    "target": 0.0,
                    "min_allowed": min_allowed,
                    "max_allowed": max_allowed,
                    "tolerance_min_pct": tol_min,
                    "tolerance_max_pct": tol_max,
                    "supply": supply,
                    "requirement": requirement,
                    "supply_pct_of_req": round(
                        supply / requirement * 100, 1
                    ) if requirement > 0 else None,
                    "unit": "Mcal/day (balance)",
                })
            elif target is not None:
                detail["min_allowed"] = target * (1 - tolerance_pct / 100)
                detail["max_allowed"] = target * (1 + tolerance_pct / 100)

            # Set actual value for non-balance attributes
            if attribute in ("mp_balance", "me_balance"):
                pass  # already set above
            elif attribute in ("dmi", "Fd_DM"):
                detail.update({
                    "actual": self._get_dmi(feed_percentages, selected_feeds),
                    "unit": "kg/day",
                })
            else:
                is_mineral = str(attribute).lower() in (
                    "fd_ca", "fd_p", "fd_mg", "fd_k", "fd_s", "fd_na", "fd_cl",
                    "ca", "p", "mg", "k", "s", "na", "cl"
                )
                dmi = self._get_dmi(feed_percentages, selected_feeds)
                conc_pct = sum(
                    feed_percentages[i] * self.feeds[f]["nutrients"].get(attribute, 0) / 100
                    for i, f in enumerate(selected_feeds)
                )
                actual = conc_pct / 100 * dmi * 1000 if is_mineral else conc_pct / 100 * dmi
                detail.update({
                    "actual": actual,
                    "unit": "g/day" if is_mineral else "kg/day",
                })

        elif c_type == "ratio":
            numerator = constraint["numerator"]
            denominator = constraint["denominator"]
            numerator_value = sum(
                feed_percentages[i] * self.feeds[f]["nutrients"].get(numerator, 0)
                for i, f in enumerate(selected_feeds)
            )
            denominator_value = sum(
                feed_percentages[i] * self.feeds[f]["nutrients"].get(denominator, 0)
                for i, f in enumerate(selected_feeds)
            )
            detail.update({
                "numerator": numerator,
                "denominator": denominator,
                "min_allowed": constraint.get("min"),
                "max_allowed": constraint.get("max"),
                "unit": "ratio",
            })
            if denominator_value < 0.001:
                detail.update({
                    "actual": None,
                    "penalty_applicable": False,
                    "note": "Denominator near zero; ratio treated as satisfied for solver compatibility.",
                })
                return self._sanitize_constraint_detail(detail)
            detail["actual"] = numerator_value / denominator_value

        else:
            detail.update({
                "penalty_applicable": False,
                "note": "Unsupported constraint type for diagnostics.",
            })
            return self._sanitize_constraint_detail(detail)

        actual = detail["actual"]
        min_allowed = detail["min_allowed"]
        max_allowed = detail["max_allowed"]
        target = detail["target"]

        if actual is None or not np.isfinite(actual):
            detail.update({
                "satisfied": False,
                "violation_direction": "unresolved",
                "violation_amount": 1.0,
                "normalized_violation": 1.0,
                "severity_percent": 100.0,
                "penalty_scale": 1.0,
                "penalty": penalty_weight,
            })
            return self._sanitize_constraint_detail(detail)

        under_violation = max(0.0, min_allowed - actual) if min_allowed is not None else 0.0
        over_violation = max(0.0, actual - max_allowed) if max_allowed is not None else 0.0
        violation_amount = under_violation + over_violation
        penalty_scale = self._constraint_scale(constraint, min_allowed, max_allowed, target)
        tolerance = self._constraint_tolerance(penalty_scale)
        if violation_amount <= tolerance:
            under_violation = 0.0
            over_violation = 0.0
            violation_amount = 0.0
        normalized_violation = violation_amount / penalty_scale

        if under_violation > 0:
            direction = "below_min"
        elif over_violation > 0:
            direction = "above_max"
        else:
            direction = None

        detail.update({
            "satisfied": violation_amount <= tolerance,
            "violation_direction": direction,
            "violation_amount": violation_amount,
            "normalized_violation": normalized_violation,
            "severity_percent": normalized_violation * 100,
            "penalty_scale": penalty_scale,
            "penalty": penalty_weight * (normalized_violation ** 2) if detail["penalty_applicable"] else 0.0,
        })
        return self._sanitize_constraint_detail(detail)

    def _evaluate_constraints(
        self,
        feed_percentages: np.ndarray,
        selected_feeds: List[str],
        nutritional_constraints: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Evaluate all nutritional constraints against a ration."""
        return [
            self._evaluate_constraint(feed_percentages, selected_feeds, constraint, index)
            for index, constraint in enumerate(nutritional_constraints, start=1)
        ]

    def _summarize_constraints(self, constraint_details: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build a compact constraint summary for tool consumers."""
        counted_constraints = [detail for detail in constraint_details if detail.get("type")]
        violated_constraints = [
            detail for detail in counted_constraints
            if not detail.get("satisfied", True) and detail.get("penalty_applicable", True)
        ]
        violated_constraints = sorted(
            violated_constraints,
            key=lambda detail: (
                detail.get("penalty", 0.0),
                detail.get("normalized_violation", 0.0),
                detail.get("violation_amount", 0.0),
            ),
            reverse=True,
        )

        return {
            "total_constraints": len(counted_constraints),
            "satisfied_constraints": len(counted_constraints) - len(violated_constraints),
            "violated_constraints": len(violated_constraints),
            "all_constraints_satisfied": len(violated_constraints) == 0,
            "total_penalty": sum(detail.get("penalty", 0.0) for detail in counted_constraints),
            "max_severity_percent": max(
                (detail.get("severity_percent", 0.0) for detail in violated_constraints),
                default=0.0,
            ),
            "top_violations": violated_constraints[:3],
        }

    def _format_constraint_summary(
        self,
        summary: Dict[str, Any],
        solution_mode: str
    ) -> str:
        """Human-readable constraint summary for the agent."""
        total_constraints = summary["total_constraints"]
        violated_constraints = summary["violated_constraints"]

        if violated_constraints == 0:
            if solution_mode == "strict":
                return f"Strict solution satisfies all {total_constraints} nutritional constraints."
            return (
                f"Fallback solution satisfies all {total_constraints} nutritional constraints "
                f"after the strict solve failed."
            )

        top_issues = []
        for detail in summary["top_violations"]:
            actual = detail.get("actual")
            actual_text = "unresolved" if actual is None else f"{actual:.3f}"
            top_issues.append(
                f"{detail['constraint_label']} {detail['violation_direction']} by "
                f"{detail['violation_amount']:.3f} {detail['unit']} (actual {actual_text})"
            )

        issues_text = "; ".join(top_issues)
        return (
            f"Compromise solution leaves {violated_constraints} of {total_constraints} nutritional "
            f"constraints unsatisfied. Worst issues: {issues_text}"
        )

    def _build_penalized_objective(
        self,
        base_objective: Callable[[np.ndarray], float],
        nutritional_constraints: List[Dict[str, Any]],
        selected_feeds: List[str]
    ) -> Callable[[np.ndarray], float]:
        """Build the compromise objective used when the strict solve fails."""
        def penalized_objective(x: np.ndarray) -> float:
            constraint_details = self._evaluate_constraints(x, selected_feeds, nutritional_constraints)
            total_penalty = sum(detail["penalty"] for detail in constraint_details)
            return base_objective(x) + total_penalty

        return penalized_objective

    def _build_initial_guess(
        self,
        n_feeds: int,
        bounds: List[Tuple[float, float]],
        candidate: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Build a stable starting point for SLSQP."""
        if candidate is not None and len(candidate) == n_feeds and np.all(np.isfinite(candidate)):
            x0 = np.clip(np.array(candidate, dtype=float), [b[0] for b in bounds], [b[1] for b in bounds])
            total = np.sum(x0)
            if total > 0:
                return x0 / total * 100.0

        return np.ones(n_feeds) * (100.0 / n_feeds)

    def _build_result_dict(
        self,
        feed_percentages: np.ndarray,
        selected_feeds: List[str],
        nutritional_constraints: List[Dict[str, Any]],
        optimization_goal: str,
        solution_mode: str,
        strict_result: Any,
        fallback_result: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Format optimization output with detailed constraint diagnostics."""
        predicted_dmi = self._get_dmi(feed_percentages, selected_feeds)

        formulation = {}
        total_cost = 0.0
        for i, feed_name in enumerate(selected_feeds):
            pct = float(feed_percentages[i])
            if pct > 0.001:
                feed_data = self.feeds[feed_name]
                dm_pct = feed_data.get("dm_percent", 100)
                kg_dm = predicted_dmi * pct / 100
                kg_fresh = kg_dm / (dm_pct / 100)

                formulation[feed_name] = {
                    "percentage_dm": round(pct, 2),
                    "kg_per_day": round(kg_fresh, 2),
                    "kg_dm_per_day": round(kg_dm, 2)
                }

                cost_per_kg_dm = feed_data.get("cost_per_kg", 0) / (dm_pct / 100)
                total_cost += pct * cost_per_kg_dm / 100

        nutrient_analysis = self._calculate_nutrient_analysis(formulation, selected_feeds)

        nasem_results = self._get_nasem_values(
            feed_percentages,
            selected_feeds,
            ["An_MPIn_g", "An_MEIn", "Mlk_Prod_MPalow", "Mlk_Prod_NEalow"]
        )
        predicted_mp = nasem_results.get("An_MPIn_g", 0.0)
        predicted_me = nasem_results.get("An_MEIn", 0.0)
        mp_milk = nasem_results.get("Mlk_Prod_MPalow", 0.0)
        ne_milk = nasem_results.get("Mlk_Prod_NEalow", 0.0)

        if mp_milk > 0 and ne_milk > 0:
            predicted_milk = min(mp_milk, ne_milk)
            if mp_milk < ne_milk:
                limiting_factor = "MP"
            elif ne_milk < mp_milk:
                limiting_factor = "NE"
            else:
                limiting_factor = "balanced"
        else:
            predicted_milk = max(mp_milk, ne_milk)
            limiting_factor = "unknown"

        constraint_details = self._evaluate_constraints(feed_percentages, selected_feeds, nutritional_constraints)
        constraint_summary = self._summarize_constraints(constraint_details)
        all_constraints_satisfied = constraint_summary["all_constraints_satisfied"]
        violated_constraints = [
            detail for detail in constraint_details
            if not detail.get("satisfied", True) and detail.get("penalty_applicable", True)
        ]

        feed_cost_per_day = self._calculate_feed_cost_per_day(feed_percentages, selected_feeds, predicted_dmi)
        base_objective = self._build_objective(selected_feeds, optimization_goal)

        # --- Core result (always included) ---
        result_dict = {
            "status": "success" if all_constraints_satisfied else "compromised",
            "solution_mode": solution_mode,
            "optimization_goal": optimization_goal,
            "formulation": formulation,
            "predicted_dmi_kg": round(predicted_dmi, 2),
            "predicted_mp_g": round(predicted_mp, 0),
            "predicted_me_mcal": round(predicted_me, 2),
            "predicted_milk_kg": round(predicted_milk, 2),
            "milk_limited_by": limiting_factor,
            "cost_per_kg_dm": round(float(total_cost), 3),
            "feed_cost_per_day": round(float(feed_cost_per_day), 2),
            "nutrient_analysis": nutrient_analysis,
            "constraint_satisfaction": self._format_constraint_summary(constraint_summary, solution_mode),
        }

        # --- Compromise-only: compact violation details ---
        if not all_constraints_satisfied:
            compact_violations = []
            for v in violated_constraints:
                entry = {
                    "constraint": v.get("constraint_label"),
                    "direction": v.get("violation_direction"),
                    "violation_amount": round(v.get("violation_amount", 0), 3),
                    "actual": round(v["actual"], 3) if isinstance(v.get("actual"), (int, float)) else v.get("actual"),
                    "unit": v.get("unit"),
                }
                # Include supply/requirement for balance constraints
                if v.get("supply") is not None:
                    entry["supply"] = round(v["supply"], 2)
                    entry["requirement"] = round(v.get("requirement", 0), 2)
                    entry["supply_pct_of_req"] = v.get("supply_pct_of_req")
                compact_violations.append(entry)
            result_dict["violations"] = compact_violations

        if optimization_goal == "maximize_profit":
            milk_price = self.animal_params.get("milk_price_per_kg", 3.0) if self.animal_params else 3.0
            milk_revenue = predicted_milk * milk_price
            result_dict["milk_revenue_per_day"] = round(float(milk_revenue), 2)
            result_dict["profit_per_day"] = round(float(milk_revenue - feed_cost_per_day), 2)

        # --- Post-optimization enrichment (one final NASEM run) ---
        if self.animal_params is not None and (all_constraints_satisfied or solution_mode in ("fallback_feasible", "strict")):
            try:
                from services.nasem_service import get_nasem_service
                nasem_service = get_nasem_service()
                
                dmi = predicted_dmi
                diet = self._build_diet_for_nasem(feed_percentages, selected_feeds, dmi)
                animal_input = nasem_service.build_animal_input(
                    body_weight_kg=self.animal_params.get("body_weight", 650.0),
                    days_in_milk=self.animal_params.get("dim", 90),
                    parity=self.animal_params.get("parity", 2),
                    target_milk_kg=self.animal_params.get("milk_prod", 35.0),
                    target_dmi_kg=dmi,
                    bcs=self.animal_params.get("bcs", 3.0),
                )
                
                enrichment = nasem_service.enrich_formulation(
                    self.feeds, diet, animal_input
                )
                if enrichment:
                    result_dict.update(enrichment)
            except Exception as e:
                logger.warning(f"Post-optimization enrichment failed: {e}")

        # --- Orientation hints ---
        hints = self._build_orientation_hints(result_dict, formulation, selected_feeds)
        if hints:
            result_dict["hints"] = hints

        return result_dict

    def _build_orientation_hints(
        self,
        result: Dict[str, Any],
        formulation: Dict[str, Dict],
        selected_feeds: List[str],
    ) -> List[str]:
        """Build short orientation reminders for the agent.

        These are NOT warnings or analyses — just quick nudges so the agent
        remembers to check important nutritional aspects.
        """
        hints: List[str] = []

        # Acidosis risk — diet starch level
        nutrient_analysis = result.get("nutrient_analysis", {})
        starch_pct = nutrient_analysis.get("Fd_St", 0)
        if starch_pct > 28:
            hints.append(
                f"Diet starch is {starch_pct:.1f}% DM — review acidosis risk "
                f"(NDF adequacy, forage particle size, starch source)."
            )
        elif starch_pct > 24:
            hints.append(
                f"Diet starch is {starch_pct:.1f}% DM — moderate level, "
                f"verify NDF is adequate for rumen health."
            )

        # Feed dominance — any single feed > 50% of ration
        for feed_name, feed_data in formulation.items():
            pct = feed_data.get("percentage_dm", 0)
            if pct > 50:
                hints.append(
                    f"'{feed_name}' makes up {pct:.0f}% of the ration — "
                    f"check if this over-reliance is intentional."
                )

        # AA reminder
        limiting_aa = result.get("limiting_aa", [])
        if limiting_aa:
            names = ", ".join(limiting_aa)
            hints.append(
                f"Limiting amino acid(s): {names}. "
                f"Consider rumen-protected AA supplements if formulation allows."
            )

        # Energy balance / body condition
        energy = result.get("energy_balance", {})
        me_balance = energy.get("me_balance_mcal")
        bw_change = energy.get("predicted_bw_change_kg_day")
        if me_balance is not None:
            bw_text = ""
            if bw_change is not None:
                bw_text = f" (~{abs(bw_change):.2f} kg/d {'loss' if bw_change < 0 else 'gain'})"
            if me_balance < -3:
                hints.append(
                    f"ME balance is {me_balance:+.1f} Mcal/d{bw_text} — cow will "
                    f"mobilize body reserves. Check if BCS loss is acceptable."
                )
            elif me_balance > 5:
                hints.append(
                    f"ME balance is {me_balance:+.1f} Mcal/d{bw_text} — excess energy, "
                    f"cow may gain condition. Verify this is appropriate for stage."
                )

        # Fat level
        fat_pct = nutrient_analysis.get("Fd_FA", 0)
        if fat_pct > 6:
            hints.append(
                f"Diet fat is {fat_pct:.1f}% DM — above 6% may depress "
                f"fiber digestion."
            )

        return hints
    
    def optimize(
        self,
        nutritional_constraints: List[Dict[str, Any]],
        selected_feeds: List[str],
        feed_constraints: Optional[Dict[str, Dict]] = None,
        optimization_goal: str = "minimize_cost"
    ) -> Dict[str, Any]:
        """
        Optimize feed formulation using SLSQP.
        
        Args:
            nutritional_constraints: List of constraint dictionaries
            selected_feeds: List of feed names to include
            feed_constraints: Optional inclusion limits {"feed_name": {"min": 0, "max": 50}}
            optimization_goal: Optimization objective:
                - "minimize_cost" (default): Find least-cost ration that meets constraints
                - "feasibility": Find any ration that meets constraints (no cost optimization)
            
        Returns:
            Dictionary with optimization results
        """
        try:
            if not selected_feeds:
                return {"error": "No feeds selected for formulation"}
            
            missing_feeds = [f for f in selected_feeds if f not in self.feeds]
            if missing_feeds:
                return {"error": f"Missing feeds in database: {missing_feeds}"}
            
            # Clear caches for this optimization run
            self._nasem_cache.clear()
            NASEMCacheStats.reset()
            self.dmi_override = None
            
            n_feeds = len(selected_feeds)
            objective = self._build_objective(selected_feeds, optimization_goal)
            
            # Equality constraint: percentages sum to 100
            def eq_constraint(x):
                return np.sum(x) - 100.0
            
            # Build inequality constraints
            ineq_constraints = []
            
            # Process DMI constraint first if present
            for constraint in nutritional_constraints:
                if constraint.get("type") == "daily_total" and constraint.get("attribute") in ("dmi", "Fd_DM"):
                    target = constraint.get("target")
                    if target is not None:
                        self.set_dmi_override(target)
                        logger.info(f"DMI override set to {target} kg")
            
            for constraint in nutritional_constraints:
                c_type = constraint.get("type", "")
                
                if c_type == "concentration":
                    nutrient = constraint["nutrient"]
                    min_val = constraint.get("min")
                    max_val = constraint.get("max")
                    
                    if min_val is not None:
                        def min_constr(x, n=nutrient, mv=min_val):
                            total = sum(x[i] * self.feeds[f]["nutrients"].get(n, 0) 
                                       for i, f in enumerate(selected_feeds))
                            return total - mv * 100
                        ineq_constraints.append({"type": "ineq", "fun": min_constr})
                    
                    if max_val is not None:
                        def max_constr(x, n=nutrient, mv=max_val):
                            total = sum(x[i] * self.feeds[f]["nutrients"].get(n, 0) 
                                       for i, f in enumerate(selected_feeds))
                            return mv * 100 - total
                        ineq_constraints.append({"type": "ineq", "fun": max_constr})
                
                elif c_type == "daily_total":
                    attribute = constraint.get("attribute")
                    target = constraint.get("target")
                    tolerance_pct = constraint.get("tolerance_percent", 3.0)
                    
                    if attribute in ("dmi", "Fd_DM"):
                        # Already handled above as DMI override
                        continue
                    
                    # Balance constraints don't need a target
                    if attribute in ("mp_balance", "me_balance"):
                        pass  # handled below
                    elif target is None:
                        continue
                    
                    if attribute == "mp_balance":
                        # MP balance constraint: supply - requirement as % of requirement
                        # tolerance_min_pct/tolerance_max_pct define allowed balance range
                        tol_min_pct = float(constraint.get("tolerance_min_pct", -tolerance_pct))
                        tol_max_pct = float(constraint.get("tolerance_max_pct", tolerance_pct))
                        
                        def mp_bal_min(x, tmin_pct=tol_min_pct):
                            supply, req, balance = self._get_nasem_mp_balance(x, selected_feeds)
                            if req <= 0:
                                return 0.0
                            return balance - (tmin_pct / 100 * req)
                        
                        def mp_bal_max(x, tmax_pct=tol_max_pct):
                            supply, req, balance = self._get_nasem_mp_balance(x, selected_feeds)
                            if req <= 0:
                                return 0.0
                            return (tmax_pct / 100 * req) - balance
                        
                        ineq_constraints.append({"type": "ineq", "fun": mp_bal_min})
                        ineq_constraints.append({"type": "ineq", "fun": mp_bal_max})
                    
                    elif attribute == "me_balance":
                        # ME balance constraint: supply - requirement as % of requirement
                        tol_min_pct = float(constraint.get("tolerance_min_pct", -tolerance_pct))
                        tol_max_pct = float(constraint.get("tolerance_max_pct", tolerance_pct))
                        
                        def me_bal_min(x, tmin_pct=tol_min_pct):
                            supply, req, balance = self._get_nasem_me_balance(x, selected_feeds)
                            if req <= 0:
                                return 0.0
                            return balance - (tmin_pct / 100 * req)
                        
                        def me_bal_max(x, tmax_pct=tol_max_pct):
                            supply, req, balance = self._get_nasem_me_balance(x, selected_feeds)
                            if req <= 0:
                                return 0.0
                            return (tmax_pct / 100 * req) - balance
                        
                        ineq_constraints.append({"type": "ineq", "fun": me_bal_min})
                        ineq_constraints.append({"type": "ineq", "fun": me_bal_max})
                    
                    else:
                        # Regular nutrient daily total (minerals, etc.)
                        # These still require a target value
                        target_min = target * (1 - tolerance_pct / 100)
                        target_max = target * (1 + tolerance_pct / 100)
                        
                        # Determine if target is in g/day (minerals) or based on % concentration
                        is_mineral = attribute.lower() in (
                            "fd_ca", "fd_p", "fd_mg", "fd_k", "fd_s", "fd_na", "fd_cl",
                            "ca", "p", "mg", "k", "s", "na", "cl"
                        )
                        
                        def daily_min(x, attr=attribute, tmin=target_min, grams=is_mineral):
                            dmi = self._get_dmi(x, selected_feeds)
                            # Diet concentration in % DM (weighted average)
                            conc_pct = sum(x[i] * self.feeds[f]["nutrients"].get(attr, 0) / 100
                                          for i, f in enumerate(selected_feeds))
                            # Daily intake calculation
                            if grams:
                                # Minerals: target in g/day, conc in %, dmi in kg
                                daily = conc_pct / 100 * dmi * 1000  # g/day
                            else:
                                # Other nutrients: target in kg/day or same units as concentration
                                daily = conc_pct / 100 * dmi  # kg/day
                            return daily - tmin
                        
                        def daily_max(x, attr=attribute, tmax=target_max, grams=is_mineral):
                            dmi = self._get_dmi(x, selected_feeds)
                            conc_pct = sum(x[i] * self.feeds[f]["nutrients"].get(attr, 0) / 100
                                          for i, f in enumerate(selected_feeds))
                            if grams:
                                daily = conc_pct / 100 * dmi * 1000  # g/day
                            else:
                                daily = conc_pct / 100 * dmi  # kg/day
                            return tmax - daily
                        
                        ineq_constraints.append({"type": "ineq", "fun": daily_min})
                        ineq_constraints.append({"type": "ineq", "fun": daily_max})
                
                elif c_type == "ratio":
                    numerator = constraint["numerator"]
                    denominator = constraint["denominator"]
                    min_ratio = constraint.get("min")
                    max_ratio = constraint.get("max")
                    
                    if min_ratio is not None:
                        def ratio_min(x, num=numerator, den=denominator, mr=min_ratio):
                            n_val = sum(x[i] * self.feeds[f]["nutrients"].get(num, 0) 
                                       for i, f in enumerate(selected_feeds))
                            d_val = sum(x[i] * self.feeds[f]["nutrients"].get(den, 0) 
                                       for i, f in enumerate(selected_feeds))
                            if d_val < 0.001:
                                return 0
                            return n_val - mr * d_val
                        ineq_constraints.append({"type": "ineq", "fun": ratio_min})
                    
                    if max_ratio is not None:
                        def ratio_max(x, num=numerator, den=denominator, mr=max_ratio):
                            n_val = sum(x[i] * self.feeds[f]["nutrients"].get(num, 0) 
                                       for i, f in enumerate(selected_feeds))
                            d_val = sum(x[i] * self.feeds[f]["nutrients"].get(den, 0) 
                                       for i, f in enumerate(selected_feeds))
                            if d_val < 0.001:
                                return 0
                            return mr * d_val - n_val
                        ineq_constraints.append({"type": "ineq", "fun": ratio_max})
            
            # Bounds for each feed
            bounds = []
            for feed_name in selected_feeds:
                min_incl = 0.0
                max_incl = 100.0
                if feed_constraints and feed_name in feed_constraints:
                    fc = feed_constraints[feed_name]
                    min_incl = fc.get("min", 0.0)
                    max_incl = fc.get("max", 100.0)
                bounds.append((min_incl, max_incl))
            
            # Initial guess - equal distribution
            x0 = self._build_initial_guess(n_feeds, bounds)
            
            # All constraints for SLSQP
            strict_constraints = [{"type": "eq", "fun": eq_constraint}] + ineq_constraints
            
            # Strict solve first: preserve the existing hard-constraint semantics.
            strict_result = minimize(
                objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=strict_constraints,
                options={'maxiter': 200, 'ftol': 1e-6}
            )
            
            if strict_result.success:
                return self._build_result_dict(
                    strict_result.x,
                    selected_feeds,
                    nutritional_constraints,
                    optimization_goal,
                    "strict",
                    strict_result,
                )

            # On the compromise path, DMI is softened like other nutrition targets.
            self.dmi_override = None
            penalized_objective = self._build_penalized_objective(
                objective,
                nutritional_constraints,
                selected_feeds,
            )
            fallback_x0 = self._build_initial_guess(
                n_feeds,
                bounds,
                candidate=getattr(strict_result, "x", None),
            )
            fallback_result = minimize(
                penalized_objective,
                fallback_x0,
                method='SLSQP',
                bounds=bounds,
                constraints=[{"type": "eq", "fun": eq_constraint}],
                options={'maxiter': 300, 'ftol': 1e-6}
            )

            if fallback_result.success:
                constraint_details = self._evaluate_constraints(
                    fallback_result.x,
                    selected_feeds,
                    nutritional_constraints,
                )
                summary = self._summarize_constraints(constraint_details)
                solution_mode = "fallback_feasible" if summary["all_constraints_satisfied"] else "fallback_compromise"
                return self._build_result_dict(
                    fallback_result.x,
                    selected_feeds,
                    nutritional_constraints,
                    optimization_goal,
                    solution_mode,
                    strict_result,
                    fallback_result,
                )

            diagnostic_result = getattr(fallback_result, "x", None)
            if diagnostic_result is None or len(diagnostic_result) != n_feeds or not np.all(np.isfinite(diagnostic_result)):
                diagnostic_result = getattr(strict_result, "x", None)

            failure_payload: Dict[str, Any] = {
                "error": (
                    f"Optimization failed. Strict solve: {strict_result.message}. "
                    f"Fallback solve: {fallback_result.message}."
                ),
                "status": "failed",
                "optimization_method": "SLSQP (strict-first with compromise fallback)",
                "strict_solver_status": "failed",
                "strict_solver_message": str(strict_result.message),
                "fallback_solver_status": "failed",
                "fallback_solver_message": str(fallback_result.message),
            }

            if diagnostic_result is not None and len(diagnostic_result) == n_feeds and np.all(np.isfinite(diagnostic_result)):
                constraint_details = self._evaluate_constraints(
                    diagnostic_result,
                    selected_feeds,
                    nutritional_constraints,
                )
                summary = self._summarize_constraints(constraint_details)
                failure_payload["constraint_summary"] = {
                    "total_constraints": summary["total_constraints"],
                    "satisfied_constraints": summary["satisfied_constraints"],
                    "violated_constraints": summary["violated_constraints"],
                    "all_constraints_satisfied": summary["all_constraints_satisfied"],
                    "total_penalty": round(float(summary["total_penalty"]), 6),
                    "max_severity_percent": round(float(summary["max_severity_percent"]), 3),
                }
                failure_payload["violated_constraints"] = summary["top_violations"]

            return failure_payload
            
        except Exception as e:
            logger.error(f"SLSQP optimization error: {e}")
            return {"error": f"Optimization error: {str(e)}", "status": "failed"}
    
    def _calculate_nutrient_analysis(
        self, 
        formulation: Dict[str, Dict], 
        selected_feeds: List[str]
    ) -> Dict[str, float]:
        """Calculate diet nutrient composition from formulation."""
        all_nutrients = set()
        for feed_name in selected_feeds:
            if feed_name in self.feeds:
                all_nutrients.update(self.feeds[feed_name].get("nutrients", {}).keys())
        
        nutrient_analysis = {}
        for nutrient in all_nutrients:
            total = 0.0
            for feed_name, data in formulation.items():
                feed_nutrients = self.feeds[feed_name].get("nutrients", {})
                nutrient_content = float(feed_nutrients.get(nutrient, 0.0))
                total += data["percentage_dm"] * nutrient_content / 100
            nutrient_analysis[nutrient] = round(total, 2)
        
        return nutrient_analysis


def create_optimizer() -> FormulationOptimizer:
    """Create a new formulation optimizer instance."""
    return FormulationOptimizer()
