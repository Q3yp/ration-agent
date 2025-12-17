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
    Calculate MP supply using NASEM 2021 kinetic CP fractionation model.
    
    An_MPIn = Dt_idRUPIn + Du_idMiTP
    
    Where:
    - Dt_idRUPIn: Intestinally digestible RUP using kinetic model
    - Du_idMiTP: Duodenal intestinally digestible microbial true protein
    
    RUP calculation uses NASEM CP fractionation (A, B, C) with passage rates:
    - Fd_RUPBIn = CPBIn * (For * KpFor/(Kd+KpFor) + Conc * KpConc/(Kd+KpConc))
    - Fd_RUPIn = (CPAIn - NPNCPIn) * fCPAdu + RUPBIn + CPCIn + IntRUP/refCPIn * CPIn
    
    NASEM coefficients from constants.py:
    - KpFor = 4.87, KpConc = 5.28 (passage rates %/h)
    - fCPAdu = 0.064, IntRUP = -0.086, refCPIn = 3.39 (RUP equation)
    - fMiTP_MiCP = 0.824, SI_dcMiCP = 0.80 (microbial protein)
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
    # NASEM coefficients for RUP kinetics
    KpFor = 4.87        # Passage rate for forage (%/h)
    KpConc = 5.28       # Passage rate for concentrate (%/h)
    fCPAdu = 0.064      # Fraction of CPA that escapes to duodenum
    IntRUP = -0.086     # RUP intercept (kg/d)
    refCPIn = 3.39      # Reference CP intake (kg/d)
    
    # NASEM coefficients for microbial protein
    fMiTP_MiCP = 0.824  # Fraction of MiCP that is true protein
    SI_dcMiCP = 0.80    # Small intestine digestibility of MiCP
    VmMiNInt = 100.8    # Vm intercept for MiN equation
    VmMiNRDPSlp = 81.56 # Vm slope for RDP
    KmMiNRDNDF = 0.0939 # Km for rumen digestible NDF
    KmMiNRDSt = 0.0274  # Km for rumen digestible starch
    
    # Accumulate diet components
    total_idrup_kg = 0.0    # Intestinally digestible RUP (kg/day)
    total_rdp_kg = 0.0      # Rumen degradable protein (kg/day)
    total_cp_kg = 0.0       # Total CP intake for intercept adjustment
    rum_dig_ndf = 0.0       # Rumen digestible NDF (kg/day)
    rum_dig_st = 0.0        # Rumen digestible starch (kg/day)
    
    for i, feed_name in enumerate(selected_feeds):
        pct = feed_percentages[i]
        nutrients = feeds[feed_name].get("nutrients", {})
        
        # Feed DM intake for this feed (kg/day)
        feed_dm_kg = dmi_kg * (pct / 100)
        
        # === CP fractionation (% of CP) - use 0 if missing (no assumptions) ===
        fd_cp = nutrients.get("Fd_CP", 0.0)           # Crude protein % DM
        fd_cparu = nutrients.get("Fd_CPARU", 0.0)     # A fraction (soluble, undegradable)
        fd_cpbru = nutrients.get("Fd_CPBRU", 0.0)     # B fraction (potentially degradable)
        fd_cpcru = nutrients.get("Fd_CPCRU", 0.0)     # C fraction (bound, unavailable)
        fd_npn_cp = nutrients.get("Fd_NPN_CP", 0.0)   # NPN as % of CP
        fd_kd_rup = nutrients.get("Fd_KdRUP", 0.0)    # Degradation rate of B fraction (%/h)
        fd_dc_rup = nutrients.get("Fd_dcRUP", 0.0)    # Intestinal digestibility of RUP (%)
        
        # Feed type for passage rate selection
        fd_conc = nutrients.get("Fd_Conc", 0.0)       # 0=forage, 100=concentrate
        fd_for = 100.0 - fd_conc                      # Forage fraction
        
        # CP intake from this feed (kg/day)
        cp_intake_kg = feed_dm_kg * (fd_cp / 100)
        total_cp_kg += cp_intake_kg
        
        # === Calculate CP fraction intakes (kg/day) ===
        cpa_in = cp_intake_kg * (fd_cparu / 100)      # A fraction intake
        cpb_in = cp_intake_kg * (fd_cpbru / 100)      # B fraction intake
        cpc_in = cp_intake_kg * (fd_cpcru / 100)      # C fraction intake
        npncp_in = cp_intake_kg * (fd_npn_cp / 100)   # NPN-CP intake
        
        # === Calculate RUP from B fraction using kinetic model ===
        # Fd_RUPBIn = CPBIn * (For/100 * Kp_For/(Kd + Kp_For) + Conc/100 * Kp_Conc/(Kd + Kp_Conc))
        rup_b_in = 0.0
        if cpb_in > 0:
            # Forage contribution
            if fd_for > 0 and (fd_kd_rup + KpFor) > 0:
                rup_b_in += cpb_in * (fd_for / 100) * KpFor / (fd_kd_rup + KpFor)
            # Concentrate contribution  
            if fd_conc > 0 and (fd_kd_rup + KpConc) > 0:
                rup_b_in += cpb_in * (fd_conc / 100) * KpConc / (fd_kd_rup + KpConc)
        
        # === Calculate total RUP intake (NASEM equation) ===
        # Fd_RUPIn = (CPA - NPNCP) * fCPAdu + RUPBIn + CPCIn + IntRUP/refCPIn * CPIn
        rup_in = ((cpa_in - npncp_in) * fCPAdu + 
                  rup_b_in + 
                  cpc_in + 
                  IntRUP / refCPIn * cp_intake_kg)
        
        # Ensure RUP is non-negative
        rup_in = max(rup_in, 0.0)
        
        # === Calculate intestinally digestible RUP ===
        idrup_kg = rup_in * (fd_dc_rup / 100)
        total_idrup_kg += idrup_kg
        
        # === Calculate RDP (CP - RUP) ===
        rdp_kg = cp_intake_kg - rup_in
        rdp_kg = max(rdp_kg, 0.0)  # Ensure non-negative
        total_rdp_kg += rdp_kg
        
        # === Rumen digestible NDF ===
        fd_ndf = nutrients.get("Fd_NDF", 0.0)
        fd_dndf48 = nutrients.get("Fd_DNDF48_NDF", 0.0)  # Use 0 if missing
        # Rumen NDF digestibility (~85% of 48h in vitro occurs in rumen)
        rum_dc_ndf = fd_dndf48 * 0.85 / 100
        ndf_intake_kg = feed_dm_kg * (fd_ndf / 100)
        rum_dig_ndf += ndf_intake_kg * rum_dc_ndf
        
        # === Rumen digestible starch ===
        fd_st = nutrients.get("Fd_St", 0.0)
        fd_dc_st = nutrients.get("Fd_dcSt", 0.0)  # Use 0 if missing
        # Rumen starch digestibility varies by source
        if fd_conc > 50:  # Concentrate
            rum_dc_st = min(fd_dc_st, 85.0) / 100
        else:  # Forage
            rum_dc_st = min(fd_dc_st, 95.0) / 100
        st_intake_kg = feed_dm_kg * (fd_st / 100)
        rum_dig_st += st_intake_kg * rum_dc_st
    
    # Ensure non-zero values for Michaelis-Menten (prevent division issues)
    rum_dig_ndf = max(rum_dig_ndf, 0.01)  # Minimum 10g
    rum_dig_st = max(rum_dig_st, 0.01)    # Minimum 10g
    
    # === Calculate microbial protein ===
    # RDP-limited Vm: RDPIn_MiNmax = min(RDPIn, DMI × 0.12) when RDP% > 12%
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
    du_micp_g = du_min_g * 6.25
    du_mitp_g = du_micp_g * fMiTP_MiCP
    du_id_mitp_g = du_mitp_g * SI_dcMiCP
    
    # Total MP supply = idRUP + idMiTP (both in g/day)
    total_idrup_g = total_idrup_kg * 1000  # Convert kg to g
    total_mp = total_idrup_g + du_id_mitp_g
    
    return total_mp


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
        """Calculate multiple NASEM values in a single model run.
        
        More efficient than separate calls when multiple values are needed.
        
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
                target_dmi_kg=dmi
            )
            
            # Call NASEM once for all values
            result = nasem_service.calculate_values(
                self.feeds, diet, animal_input, param_names
            )
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