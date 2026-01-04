import numpy as np
from scipy.optimize import minimize
from typing import Dict, List, Any, Optional, Tuple
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
    - ratio: ratios between nutrients
    - inclusion: feed inclusion limits
    
    For dairy cows, can:
    - Predict DMI from diet composition using NASEM equation 9
    - Calculate MP supply from diet for MP constraints (g/day)
    - Calculate ME supply from diet for ME constraints (Mcal/day)
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
    def _get_nasem_mp(self, feed_percentages: np.ndarray, selected_feeds: List[str]) -> float:
        """Get MP from NASEM. Returns An_MPIn_g in g/day."""
        result = self._get_nasem_values(feed_percentages, selected_feeds, ["An_MPIn_g"])
        return result.get("An_MPIn_g", 0.0)
    
    def _get_nasem_me(self, feed_percentages: np.ndarray, selected_feeds: List[str]) -> float:
        """Get ME from NASEM. Returns An_MEIn in Mcal/day."""
        result = self._get_nasem_values(feed_percentages, selected_feeds, ["An_MEIn"])
        return result.get("An_MEIn", 0.0)
    
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
            
            n_feeds = len(selected_feeds)
            
            # Objective function based on optimization goal
            if optimization_goal == "feasibility":
                # Just find any feasible solution - constant objective
                def objective(x):
                    return 0.0
            elif optimization_goal == "maximize_profit":
                # Maximize profit = milk revenue - feed cost
                milk_price = self.animal_params.get("milk_price_per_kg", 3.0) if self.animal_params else 3.0
                
                def objective(x):
                    # Calculate total feed cost
                    dmi = self._get_dmi(x, selected_feeds)
                    total_feed_cost = 0.0
                    for i, feed_name in enumerate(selected_feeds):
                        feed_data = self.feeds[feed_name]
                        dm_pct = feed_data.get("dm_percent", 100)
                        cost_per_kg_dm = feed_data.get("cost_per_kg", 0) / (dm_pct / 100)
                        kg_dm = dmi * x[i] / 100
                        total_feed_cost += kg_dm * cost_per_kg_dm
                    
                    # Calculate milk revenue using least-constraint milk
                    predicted_milk = self._get_nasem_milk_prod(x, selected_feeds)
                    milk_revenue = predicted_milk * milk_price
                    
                    # Profit = revenue - cost, return negative for minimization
                    profit = milk_revenue - total_feed_cost
                    return -profit  # Minimize negative profit = maximize profit
            else:
                # Default: minimize cost per kg DM
                def objective(x):
                    total_cost = 0.0
                    for i, feed_name in enumerate(selected_feeds):
                        feed_data = self.feeds[feed_name]
                        cost_per_kg_dm = feed_data.get("cost_per_kg", 0) / (feed_data.get("dm_percent", 100) / 100)
                        total_cost += x[i] * cost_per_kg_dm / 100
                    return total_cost
            
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
                    
                    if target is None:
                        continue
                    
                    target_min = target * (1 - tolerance_pct / 100)
                    target_max = target * (1 + tolerance_pct / 100)
                    
                    if attribute == "mp":
                        # Metabolizable Protein constraint using full NASEM model
                        def mp_min(x, tmin=target_min):
                            mp_supply = self._get_nasem_mp(x, selected_feeds)
                            return mp_supply - tmin
                        
                        def mp_max(x, tmax=target_max):
                            mp_supply = self._get_nasem_mp(x, selected_feeds)
                            return tmax - mp_supply
                        
                        ineq_constraints.append({"type": "ineq", "fun": mp_min})
                        ineq_constraints.append({"type": "ineq", "fun": mp_max})
                    
                    elif attribute == "me":
                        # Metabolizable Energy constraint using full NASEM model (Mcal/day)
                        def me_min(x, tmin=target_min):
                            me_supply = self._get_nasem_me(x, selected_feeds)
                            return me_supply - tmin
                        
                        def me_max(x, tmax=target_max):
                            me_supply = self._get_nasem_me(x, selected_feeds)
                            return tmax - me_supply
                        
                        ineq_constraints.append({"type": "ineq", "fun": me_min})
                        ineq_constraints.append({"type": "ineq", "fun": me_max})
                    
                    else:
                        # Regular nutrient daily total
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
            x0 = np.ones(n_feeds) * (100.0 / n_feeds)
            
            # All constraints for SLSQP
            constraints = [{"type": "eq", "fun": eq_constraint}] + ineq_constraints
            
            # Optimize
            result = minimize(
                objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 200, 'ftol': 1e-6}
            )
            
            if not result.success:
                return {"error": f"Optimization failed: {result.message}", "status": "failed"}
            
            # Format results
            feed_percentages = result.x
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
            
            # Calculate nutrient analysis
            nutrient_analysis = self._calculate_nutrient_analysis(formulation, selected_feeds)
            
            # Calculate predicted MP, ME, and milk production using NASEM (single model run)
            nasem_results = self._get_nasem_values(
                feed_percentages, selected_feeds, 
                ["An_MPIn_g", "An_MEIn", "Mlk_Prod_MPalow", "Mlk_Prod_NEalow"]
            )
            predicted_mp = nasem_results.get("An_MPIn_g", 0.0)
            predicted_me = nasem_results.get("An_MEIn", 0.0)
            mp_milk = nasem_results.get("Mlk_Prod_MPalow", 0.0)
            ne_milk = nasem_results.get("Mlk_Prod_NEalow", 0.0)
            
            # Determine predicted milk and limiting factor
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
            
            result_dict = {
                "status": "success",
                "formulation": formulation,
                "predicted_dmi_kg": round(predicted_dmi, 2),
                "predicted_mp_g": round(predicted_mp, 0),
                "predicted_me_mcal": round(predicted_me, 2),
                "predicted_milk_kg": round(predicted_milk, 2),
                "milk_limited_by": limiting_factor,
                "cost_per_kg_dm": round(float(total_cost), 3),
                "nutrient_analysis": nutrient_analysis,
                "optimization_method": "SLSQP",
                "constraint_satisfaction": "All constraints satisfied"
            }
            
            # Add animal params if used
            if self.animal_params:
                result_dict["animal_params_used"] = self.animal_params
            if self.dmi_override:
                result_dict["dmi_override_kg"] = self.dmi_override
            
            return result_dict
            
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