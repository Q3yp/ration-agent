import numpy as np
from scipy.optimize import minimize
from typing import Dict, List, Any, Optional
import json
import logging
import math

logger = logging.getLogger(__name__)


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


def calculate_mp_supply(
    feed_percentages: np.ndarray,
    feeds: Dict[str, Dict],
    selected_feeds: List[str],
    dmi_kg: float
) -> float:
    """
    Calculate MP supply using NASEM 2021 equation (Eq 20-136).
    
    An_MPIn = Dt_idRUPIn + Du_idMiTP
    
    Where:
    - Dt_idRUPIn: Intestinally digestible RUP (sum of feed contributions)
    - Du_idMiTP: Duodenal intestinally digestible microbial true protein
    
    Microbial N uses NRC2021 Michaelis-Menten equation:
    Du_MiN = Vm / (1 + Km_NDF/Rum_DigNDF + Km_St/Rum_DigSt)
    
    NASEM coefficients:
    - fMiTP_MiCP = 0.824 (fraction of MiCP that is true protein)
    - SI_dcMiCP = 0.80 (small intestine digestibility of MiCP)
    - VmMiNInt = 100.8, VmMiNRDPSlp = 81.56 (Vm equation)
    - KmMiNRDNDF = 0.0939, KmMiNRDSt = 0.0274 (Km constants)
    
    Args:
        feed_percentages: Array of feed inclusion percentages (sum to 100)
        feeds: Feed database with nutrient compositions
        selected_feeds: List of feed names in same order as percentages
        dmi_kg: Dry matter intake in kg/day
        
    Returns:
        Estimated MP supply in g/day
    """
    # NASEM coefficients
    fMiTP_MiCP = 0.824  # Fraction of MiCP that is true protein
    SI_dcMiCP = 0.80    # Small intestine digestibility of MiCP
    VmMiNInt = 100.8    # Vm intercept for MiN equation
    VmMiNRDPSlp = 81.56 # Vm slope for RDP
    KmMiNRDNDF = 0.0939 # Km for rumen digestible NDF
    KmMiNRDSt = 0.0274  # Km for rumen digestible starch
    
    # Accumulate diet components
    total_idrup = 0.0       # Intestinally digestible RUP (kg/day)
    total_rdp_kg = 0.0      # Rumen degradable protein (kg/day)
    rum_dig_ndf = 0.0       # Rumen digestible NDF (kg/day)
    rum_dig_st = 0.0        # Rumen digestible starch (kg/day)
    
    for i, feed_name in enumerate(selected_feeds):
        pct = feed_percentages[i]
        nutrients = feeds[feed_name].get("nutrients", {})
        
        # Feed DM intake for this feed
        feed_dm_kg = dmi_kg * (pct / 100)
        
        # Feed crude protein % DM
        fd_cp = nutrients.get("Fd_CP", 0.0)
        
        # RUP calculation using CP fractions
        # Fd_CPARU = CP A fraction (rumen unavailable/undegradable)
        # In NASEM, RUP = CP_A + CP_C (undegraded B fraction negligible for simplicity)
        fd_cparu = nutrients.get("Fd_CPARU", 30.0)  # Default 30% undegradable
        fd_cpcru = nutrients.get("Fd_CPCRU", 5.0)   # C fraction (bound, unavailable)
        
        # RUP as fraction of CP (A fraction is the main undegradable portion)
        rup_fraction = fd_cparu / 100  # Convert to fraction
        
        # RUP intake from this feed (kg/day)
        cp_intake_kg = feed_dm_kg * (fd_cp / 100)
        rup_intake_kg = cp_intake_kg * rup_fraction
        
        # RUP digestibility (%)
        fd_dc_rup = nutrients.get("Fd_dcRUP", 75.0)  # Default 75%
        
        # Intestinally digestible RUP (kg/day)
        idrup_kg = rup_intake_kg * (fd_dc_rup / 100)
        total_idrup += idrup_kg
        
        # RDP calculation (CP - RUP)
        rdp_intake_kg = cp_intake_kg * (1 - rup_fraction)
        total_rdp_kg += rdp_intake_kg
        
        # Rumen digestible NDF
        fd_ndf = nutrients.get("Fd_NDF", 0.0)
        # Use Fd_DNDF48_NDF if available, else estimate 48% digestibility
        fd_dndf48 = nutrients.get("Fd_DNDF48_NDF", 48.0)
        # Rumen NDF digestibility approximation (slightly lower than total tract)
        rum_dc_ndf = fd_dndf48 * 0.85 / 100  # ~85% of 48h in vitro occurs in rumen
        ndf_intake_kg = feed_dm_kg * (fd_ndf / 100)
        rum_dig_ndf += ndf_intake_kg * rum_dc_ndf
        
        # Rumen digestible starch
        fd_st = nutrients.get("Fd_St", 0.0)
        # Use Fd_dcSt if available, else estimate based on feed type
        fd_dc_st = nutrients.get("Fd_dcSt", 92.0)  # Default 92% total tract
        fd_conc = nutrients.get("Fd_Conc", 50.0)   # 0=forage, 100=concentrate
        # Rumen starch digestibility varies by source
        if fd_conc > 50:  # Concentrate
            rum_dc_st = min(fd_dc_st, 85.0) / 100  # ~85% max in rumen for concentrates
        else:  # Forage
            rum_dc_st = min(fd_dc_st, 95.0) / 100  # Higher for silages
        st_intake_kg = feed_dm_kg * (fd_st / 100)
        rum_dig_st += st_intake_kg * rum_dc_st
    
    # Ensure non-zero values for Michaelis-Menten (prevent division issues)
    rum_dig_ndf = max(rum_dig_ndf, 0.01)  # Minimum 10g
    rum_dig_st = max(rum_dig_st, 0.01)    # Minimum 10g
    
    # Calculate RDP-limited Vm for microbial N
    # RDPIn_MiNmax = min(RDPIn, DMI × 0.12) when RDP% > 12%
    an_rdp_pct = (total_rdp_kg / dmi_kg) * 100 if dmi_kg > 0 else 12.0
    if an_rdp_pct <= 12:
        rdpin_minmax = total_rdp_kg
    else:
        rdpin_minmax = dmi_kg * 0.12
    
    # Vm = VmMiNInt + VmMiNRDPSlp × RDPIn_MiNmax
    min_vm = VmMiNInt + VmMiNRDPSlp * rdpin_minmax
    
    # Duodenal microbial N (NRC2021 equation) in g/day
    # Du_MiN = Vm / (1 + Km_NDF/Rum_DigNDF + Km_St/Rum_DigSt)
    du_min_g = min_vm / (1 + KmMiNRDNDF / rum_dig_ndf + KmMiNRDSt / rum_dig_st)
    
    # Limit MiN by RDP availability (MiN cannot exceed RDP/6.25)
    rdp_n_limit = total_rdp_kg * 1000 / 6.25  # g N from RDP
    du_min_g = min(du_min_g, rdp_n_limit)
    
    # Convert MiN to intestinally digestible MiTP
    # Du_MiCP = Du_MiN × 6.25
    du_micp_g = du_min_g * 6.25
    
    # Du_MiTP = Du_MiCP × fMiTP_MiCP (true protein fraction)
    du_mitp_g = du_micp_g * fMiTP_MiCP
    
    # Du_idMiTP = Du_MiTP × SI_dcMiCP (intestinal digestibility)
    du_id_mitp_g = du_mitp_g * SI_dcMiCP
    
    # Total MP supply = idRUP + idMiTP (both in g/day)
    total_idrup_g = total_idrup * 1000  # Convert kg to g
    total_mp = total_idrup_g + du_id_mitp_g
    
    return total_mp


class FormulationOptimizer:
    """
    Feed formulation optimizer using SLSQP (Sequential Least Squares Programming).
    
    Supports:
    - concentration: nutrient % of dry matter
    - daily_total: absolute daily nutrient intake (including mp, dmi)
    - ratio: ratios between nutrients
    - inclusion: feed inclusion limits
    
    For dairy cows, can:
    - Predict DMI from diet composition using NASEM equation 9
    - Calculate MP supply from diet for MP constraints
    """
    
    def __init__(self):
        self.feeds = {}
        self.constraints = []
        self.optimization_goal = "minimize_cost"
        self.animal_params = None
        self.dmi_override = None  # Optional DMI override value
    
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
        milk_protein_pct: float = 3.2
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
            "ne_milk_out": ne_milk_out
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
    
    def optimize(
        self,
        nutritional_constraints: List[Dict[str, Any]],
        selected_feeds: List[str],
        feed_constraints: Optional[Dict[str, Dict]] = None,
        optimization_goal: str = "minimize_cost",
        use_dmi_prediction: bool = True  # Kept for backward compatibility
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
            use_dmi_prediction: Ignored (always uses SLSQP now)
            
        Returns:
            Dictionary with optimization results
        """
        try:
            if not selected_feeds:
                return {"error": "No feeds selected for formulation"}
            
            missing_feeds = [f for f in selected_feeds if f not in self.feeds]
            if missing_feeds:
                return {"error": f"Missing feeds in database: {missing_feeds}"}
            
            n_feeds = len(selected_feeds)
            
            # Objective function based on optimization goal
            if optimization_goal == "feasibility":
                # Just find any feasible solution - constant objective
                def objective(x):
                    return 0.0
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
                    tolerance_pct = constraint.get("tolerance_percent", 10.0)
                    
                    if attribute in ("dmi", "Fd_DM"):
                        # Already handled above as DMI override
                        continue
                    
                    if target is None:
                        continue
                    
                    target_min = target * (1 - tolerance_pct / 100)
                    target_max = target * (1 + tolerance_pct / 100)
                    
                    if attribute == "mp":
                        # Metabolizable Protein constraint
                        def mp_min(x, tmin=target_min):
                            dmi = self._get_dmi(x, selected_feeds)
                            mp_supply = calculate_mp_supply(x, self.feeds, selected_feeds, dmi)
                            return mp_supply - tmin
                        
                        def mp_max(x, tmax=target_max):
                            dmi = self._get_dmi(x, selected_feeds)
                            mp_supply = calculate_mp_supply(x, self.feeds, selected_feeds, dmi)
                            return tmax - mp_supply
                        
                        ineq_constraints.append({"type": "ineq", "fun": mp_min})
                        ineq_constraints.append({"type": "ineq", "fun": mp_max})
                    
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
            
            # Calculate predicted MP supply
            predicted_mp = calculate_mp_supply(
                feed_percentages, self.feeds, selected_feeds, predicted_dmi
            )
            
            result_dict = {
                "status": "success",
                "formulation": formulation,
                "predicted_dmi_kg": round(predicted_dmi, 2),
                "predicted_mp_g": round(predicted_mp, 0),
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