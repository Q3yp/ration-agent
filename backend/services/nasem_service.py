"""NASEM Dairy Model Service.

Minimal wrapper for the NASEM 2021 Dairy Cattle Model.
Takes feedbase dict as input - no internal loading.
Returns raw NASEM output - agent interprets results.
"""

import logging
from typing import Dict, Any, Optional, List

import pandas as pd
import numpy as np
from nasem_dairy.model.nasem import nasem

logger = logging.getLogger(__name__)


class NASEMService:
    """Minimal service for NASEM dairy model calculations."""
    
    # Default equation selection
    DEFAULT_EQUATION_SELECTION = {
        "Use_DNDF_IV": 0,
        "DMIn_eqn": 0,
        "mProd_eqn": 1,
        "MiN_eqn": 1,
        "NonMilkCP_ClfLiq": 0,
        "Monensin_eqn": 0,
        "mPrt_eqn": 0,
        "mFat_eqn": 1,
        "RumDevDisc_Clf": 0
    }
    
    # Default infusion input (no infusions)
    DEFAULT_INFUSION_INPUT = {
        "Inf_Acet_g": 0.0, "Inf_ADF_g": 0.0, "Inf_Arg_g": 0.0, "Inf_Ash_g": 0.0,
        "Inf_Butr_g": 0.0, "Inf_CP_g": 0.0, "Inf_CPARum_CP": 0.0, "Inf_CPBRum_CP": 0.0,
        "Inf_CPCRum_CP": 0.0, "Inf_dcFA": 0.0, "Inf_dcRUP": 0.0, "Inf_DM_g": 0.0,
        "Inf_EE_g": 0.0, "Inf_FA_g": 0.0, "Inf_Glc_g": 0.0, "Inf_His_g": 0.0,
        "Inf_Ile_g": 0.0, "Inf_KdCPB": 0.0, "Inf_Leu_g": 0.0, "Inf_Lys_g": 0.0,
        "Inf_Met_g": 0.0, "Inf_NDF_g": 0.0, "Inf_NPNCP_g": 0.0, "Inf_Phe_g": 0.0,
        "Inf_Prop_g": 0.0, "Inf_St_g": 0.0, "Inf_Thr_g": 0.0, "Inf_Trp_g": 0.0,
        "Inf_ttdcSt": 0.0, "Inf_Val_g": 0.0, "Inf_VFA_g": 0.0, "Inf_Location": "Rumen"
    }
    
    def build_feed_library(self, feedbase: Dict[str, Any], feed_keys: Optional[List[str]] = None) -> pd.DataFrame:
        """Build feed library DataFrame from feedbase dict.
        
        Args:
            feedbase: Feedbase dict with structure: {"feeds": {feed_key: {...}}}
            feed_keys: Optional list of feed keys to include. If None, includes all.
        
        Returns:
            DataFrame in NASEM feed library format with all required columns
        """
        from nasem_dairy.model.input_definitions import FeedLibrarySchema
        
        feeds = feedbase.get("feeds", {})
        if not feeds:
            raise ValueError("Empty feedbase provided")
        
        rows = []
        for feed_key, feed_data in feeds.items():
            if feed_keys is not None and feed_key not in feed_keys:
                continue
                
            row = dict(feed_data.get("nutrients", {}))
            row["Fd_Name"] = feed_data.get("nasem_name", feed_key)
            row["Fd_Category"] = feed_data.get("category", "")
            row["Fd_Type"] = feed_data.get("type", "")
            row["Fd_Libr"] = feed_data.get("Fd_Libr", "Custom")
            row["UID"] = feed_data.get("UID", f"CUSTOM_{feed_key}")
            row["Fd_Index"] = feed_data.get("Fd_Index", 0)
            row["Fd_Locked"] = feed_data.get("Fd_Locked", 0)
            if "Fd_DM" not in row:
                row["Fd_DM"] = feed_data.get("dm_percent", 90.0)
            rows.append(row)
        
        if not rows:
            raise ValueError(f"No matching feeds found for keys: {feed_keys}")
        
        df = pd.DataFrame(rows)
        
        # Ensure all required columns from FeedLibrarySchema exist
        # Add missing columns with appropriate default values
        for col, col_type in FeedLibrarySchema.items():
            if col not in df.columns:
                if col_type == str:
                    df[col] = ""
                else:  # float or int
                    df[col] = 0
        
        # Fill NaN values in numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)
        return df
    
    def build_animal_input(
        self,
        body_weight_kg: float,
        days_in_milk: int,
        parity: int,
        target_milk_kg: float,
        milk_fat_percent: float = 3.5,
        milk_protein_percent: float = 3.2,
        days_pregnant: int = 0,
        breed: str = "Holstein",
        target_dmi_kg: Optional[float] = None,
        bcs: float = 3.0
    ) -> Dict[str, Any]:
        """Build animal input dict for NASEM model."""
        if target_dmi_kg is None:
            target_dmi_kg = body_weight_kg * 0.035 + target_milk_kg * 0.1
        
        age_days = 730 + (parity - 1) * 365 + days_in_milk
        state = "Dry Cow" if days_pregnant > 220 else "Lactating Cow"
        
        return {
            "An_Parity_rl": float(parity),
            "Trg_MilkProd": 0.0 if state == "Dry Cow" else float(target_milk_kg),
            "An_BW": float(body_weight_kg),
            "An_BCS": float(bcs),
            "An_LactDay": int(days_in_milk),
            "Trg_MilkFatp": float(milk_fat_percent),
            "Trg_MilkTPp": float(milk_protein_percent),
            "Trg_MilkLacp": 4.85,
            "Trg_Dt_DMIn": float(target_dmi_kg),
            "An_BW_mature": float(body_weight_kg),
            "Trg_FrmGain": 0.0,
            "An_GestDay": int(days_pregnant),
            "An_GestLength": 280,
            "Trg_RsrvGain": 0.0,
            "Fet_BWbrth": 44.1,
            "An_AgeDay": float(age_days),
            "An_305RHA_MlkTP": 480,
            "An_StatePhys": state,
            "An_Breed": breed if breed in ["Holstein", "Jersey", "Other"] else "Holstein",
            "An_AgeDryFdStart": 14,
            "Env_TempCurr": 22.0,
            "Env_DistParlor": 0,
            "Env_TripsParlor": 0,
            "Env_Topo": 0,
            "An_AgeConcept1st": 480,
        }
    
    @staticmethod
    def build_diet_from_formulation(formulation_result: Dict[str, Any]) -> tuple[Dict[str, float], float]:
        """Build diet composition from optimizer formulation result.
        
        This is the SINGLE SOURCE OF TRUTH for converting formulation results to
        NASEM diet format. All callers should use this function to prevent
        mismatches between diet composition and DMI.
        
        Args:
            formulation_result: The full formulation result dict from optimizer,
                containing 'formulation' (dict of feeds) and 'predicted_dmi_kg'
        
        Returns:
            Tuple of (diet_composition, predicted_dmi_kg):
            - diet_composition: {feed_key: kg_dm_per_day} for NASEM
            - predicted_dmi_kg: Total DMI in kg/day (matches sum of diet)
        
        Raises:
            ValueError if formulation is missing or incomplete
        """
        if not formulation_result or formulation_result.get("status") != "success":
            raise ValueError("Invalid or unsuccessful formulation result")
        
        formulation_feeds = formulation_result.get("formulation", {})
        if not formulation_feeds:
            raise ValueError("No formulation feeds found")
        
        predicted_dmi_kg = formulation_result.get("predicted_dmi_kg")
        if not predicted_dmi_kg:
            raise ValueError("No predicted_dmi_kg found in formulation")
        
        # Build diet using kg_dm_per_day (DM weight) - MUST match Trg_Dt_DMIn
        diet_composition = {}
        for feed_name, feed_data in formulation_feeds.items():
            kg_dm_per_day = feed_data.get("kg_dm_per_day", 0)
            if kg_dm_per_day and kg_dm_per_day > 0:
                diet_composition[feed_name] = kg_dm_per_day
        
        if not diet_composition:
            raise ValueError("No valid kg_dm_per_day values in formulation")
        
        return diet_composition, float(predicted_dmi_kg)
    
    def calculate_requirements(
        self,
        feedbase: Dict[str, Any],
        reference_diet: Dict[str, float],
        animal_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate nutrient requirements using NASEM model.
        
        Args:
            feedbase: Feedbase dict from store
            reference_diet: Dict of {feed_key: kg_dm_per_day} for reference diet
            animal_input: Animal parameters dict
        
        Returns:
            Raw NASEM output values - agent interprets results.
        """
        try:
            # Build user diet DataFrame  
            user_diet = pd.DataFrame({
                "Feedstuff": [feedbase["feeds"][k].get("nasem_name", k) for k in reference_diet.keys()],
                "kg_user": list(reference_diet.values())
            })
            
            # Build feed library for these feeds only
            feed_library = self.build_feed_library(feedbase, list(reference_diet.keys()))
            
            # Run NASEM
            output = nasem(
                user_diet=user_diet,
                animal_input=animal_input,
                equation_selection=self.DEFAULT_EQUATION_SELECTION,
                feed_library=feed_library,
                infusion_input=self.DEFAULT_INFUSION_INPUT
            )
            
            return {
                "status": "success",
                "snapshot": str(output)
            }
            
        except Exception as e:
            logger.error(f"Error calculating requirements: {e}")
            return {"status": "error", "error": str(e)}
    
    def evaluate_diet(
        self,
        feedbase: Dict[str, Any],
        diet_composition: Dict[str, float],
        animal_input: Dict[str, Any],
        return_full_output: bool = False
    ) -> Dict[str, Any]:
        """Evaluate a diet using NASEM model.
        
        Args:
            feedbase: Feedbase dict from store
            diet_composition: {feed_key: kg_dm_per_day}
            animal_input: Animal parameters dict
            return_full_output: If True, returns full ModelOutput object for export
        
        Returns:
            Raw NASEM output values - agent interprets results.
        """
        try:
            # Build user diet DataFrame
            user_diet = pd.DataFrame({
                "Feedstuff": [feedbase["feeds"][k].get("nasem_name", k) for k in diet_composition.keys()],
                "kg_user": list(diet_composition.values())
            })
            
            # Build feed library for these feeds only
            feed_library = self.build_feed_library(feedbase, list(diet_composition.keys()))
            
            # Run NASEM
            output = nasem(
                user_diet=user_diet,
                animal_input=animal_input,
                equation_selection=self.DEFAULT_EQUATION_SELECTION,
                feed_library=feed_library,
                infusion_input=self.DEFAULT_INFUSION_INPUT
            )
            
            result = {
                "status": "success",
                "snapshot": str(output),
                "diet_summary": {
                    "total_fresh_intake_kg": sum(diet_composition.values()),  # Fresh (as-fed) weight from formulation
                    "feed_count": len(diet_composition),
                }
            }
            
            # Include full output for Excel export
            if return_full_output:
                result["model_output"] = output
            
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating diet: {e}")
            return {"status": "error", "error": str(e)}
    
    def enrich_formulation(
        self,
        feedbase: Dict[str, Any],
        diet_composition: Dict[str, float],
        animal_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run NASEM once and extract enrichment data for a formulation result.
        
        Extracts information the optimizer doesn't surface on its own:
        - Amino acid balance (Lys, Met as % of MP and absorbed g)
        - Energy balance (ME intake vs use → weight gain/loss implication)
        - RDP status
        - Starch-related rumen data
        
        Args:
            feedbase: Feedbase dict OR direct feeds dict {feed_key: {...}}
            diet_composition: {feed_key: kg_dm_per_day}
            animal_input: Animal input dict (from build_animal_input)
        
        Returns:
            Dict with enrichment data, or empty dict on failure.
        """
        try:
            # Handle both feedbase format and direct feeds dict
            if "feeds" not in feedbase:
                feedbase = {"feeds": feedbase}
            feeds = feedbase["feeds"]
            
            user_diet = pd.DataFrame({
                "Feedstuff": [feeds[k].get("nasem_name", k) for k in diet_composition.keys()],
                "kg_user": list(diet_composition.values())
            })
            feed_library = self.build_feed_library(feedbase, list(diet_composition.keys()))
            
            output = nasem(
                user_diet=user_diet,
                animal_input=animal_input,
                equation_selection=self.DEFAULT_EQUATION_SELECTION,
                feed_library=feed_library,
                infusion_input=self.DEFAULT_INFUSION_INPUT
            )
            
            enrichment: Dict[str, Any] = {}
            
            # --- Amino Acid Balance ---
            AA_TARGETS = {"Lys": 7.2, "Met": 2.5}  # NASEM 2021 targets (% of MP)
            try:
                abs_aa_mpp = output.get_value("Abs_AA_MPp")   # pd.Series: AA → % of MP
                abs_aa_g = output.get_value("Abs_AA_g")       # pd.Series: AA → g/day
                trg_abs_aa = output.get_value("Trg_AbsAA_g")  # pd.Series: AA → target g/day
                
                if abs_aa_mpp is not None and abs_aa_g is not None:
                    aa_status = {}
                    limiting_aa = []
                    for aa, target_pct in AA_TARGETS.items():
                        pct_mp = round(float(abs_aa_mpp.get(aa, 0)), 2)
                        absorbed_g = round(float(abs_aa_g.get(aa, 0)), 1)
                        target_g = round(float(trg_abs_aa.get(aa, 0)), 1) if trg_abs_aa is not None else None
                        aa_status[aa.lower()] = {
                            "pct_mp": pct_mp,
                            "target_pct_mp": target_pct,
                            "absorbed_g": absorbed_g,
                        }
                        if target_g is not None:
                            aa_status[aa.lower()]["target_g"] = target_g
                        if pct_mp < target_pct:
                            limiting_aa.append(aa)
                    enrichment["amino_acid_balance"] = aa_status
                    enrichment["limiting_aa"] = limiting_aa
            except Exception as e:
                logger.warning(f"Failed to extract AA data: {e}")
            
            # --- Energy Balance ---
            try:
                me_intake = output.get_value("An_MEIn")       # Mcal/day
                me_target = output.get_value("Trg_MEuse")     # Mcal/day (target total use)
                me_maint = output.get_value("An_MEmUse")      # Mcal/day (maintenance)
                
                if me_intake is not None and me_target is not None:
                    me_balance = float(me_intake) - float(me_target)
                    enrichment["energy_balance"] = {
                        "me_intake_mcal": round(float(me_intake), 2),
                        "me_target_use_mcal": round(float(me_target), 2),
                        "me_balance_mcal": round(me_balance, 2),
                    }
                    if me_maint is not None:
                        enrichment["energy_balance"]["me_maintenance_mcal"] = round(float(me_maint), 2)
                    
                    # Body reserve change
                    rsrv_gain = output.get_value("Rsrv_Gain_empty")
                    body_gain = output.get_value("Body_Gain_empty")
                    if body_gain is not None:
                        enrichment["energy_balance"]["body_gain_kg_day"] = round(float(body_gain), 3)
                    if rsrv_gain is not None:
                        enrichment["energy_balance"]["reserve_gain_kg_day"] = round(float(rsrv_gain), 3)
            except Exception as e:
                logger.warning(f"Failed to extract energy balance: {e}")
            
            # --- RDP Status ---
            try:
                rdp_intake = output.get_value("An_RDPIn_g")
                if rdp_intake is not None:
                    enrichment["rdp_intake_g"] = round(float(rdp_intake), 0)
            except Exception:
                pass
            
            # --- Rumen Starch ---
            try:
                rum_dig_st = output.get_value("Rum_DigStIn")
                if rum_dig_st is not None:
                    enrichment["rumen_digested_starch_kg"] = round(float(rum_dig_st), 2)
            except Exception:
                pass
            
            return enrichment
            
        except Exception as e:
            logger.warning(f"Formulation enrichment failed: {e}")
            return {}
    
    def calculate_values(
        self,
        feedbase: Dict[str, Any],
        diet_composition: Dict[str, float],
        animal_input: Dict[str, Any],
        param_names: List[str]
    ) -> Dict[str, float]:
        """Calculate multiple NASEM values in a single model run.
        
        Generalized method that runs NASEM once and extracts requested parameters.
        More efficient than calling separate methods when multiple values are needed.
        
        Args:
            feedbase: Feedbase dict with structure {"feeds": {feed_key: {...}}}
                     OR just the feeds dict {feed_key: {...}} - will be wrapped
            diet_composition: {feed_key: kg_dm_per_day}
            animal_input: Animal input dict (from build_animal_input)
            param_names: List of NASEM parameter names to extract, e.g.:
                        ["An_MPIn_g", "An_MEIn", "Mlk_Prod_comp"]
        
        Returns:
            Dict of {param_name: value} for each requested parameter.
            Missing/error values are set to 0.0
        """
        result = {name: 0.0 for name in param_names}
        
        try:
            # Handle both feedbase format and direct feeds dict
            if "feeds" in feedbase:
                feeds = feedbase["feeds"]
            else:
                # Direct feeds dict passed - wrap it
                feeds = feedbase
                feedbase = {"feeds": feeds}
            
            # Build user diet DataFrame
            user_diet = pd.DataFrame({
                "Feedstuff": [feeds[k].get("nasem_name", k) for k in diet_composition.keys()],
                "kg_user": list(diet_composition.values())
            })
            
            # Build feed library for these feeds only
            feed_library = self.build_feed_library(feedbase, list(diet_composition.keys()))
            
            # Run NASEM once
            output = nasem(
                user_diet=user_diet,
                animal_input=animal_input,
                equation_selection=self.DEFAULT_EQUATION_SELECTION,
                feed_library=feed_library,
                infusion_input=self.DEFAULT_INFUSION_INPUT
            )
            
            # Extract all requested values
            for param_name in param_names:
                value = output.get_value(param_name)
                if value is not None:
                    result[param_name] = float(value)
            
            return result
            
        except Exception as e:
            logger.warning(f"Error calculating NASEM values: {e}")
            return result
    
    # Convenience wrappers for common cases
    def calculate_mp(
        self,
        feedbase: Dict[str, Any],
        diet_composition: Dict[str, float],
        animal_input: Dict[str, Any]
    ) -> float:
        """Calculate MP supply using full NASEM model. Returns An_MPIn_g in g/day."""
        result = self.calculate_values(feedbase, diet_composition, animal_input, ["An_MPIn_g"])
        return result.get("An_MPIn_g", 0.0)
    
    def calculate_me(
        self,
        feedbase: Dict[str, Any],
        diet_composition: Dict[str, float],
        animal_input: Dict[str, Any]
    ) -> float:
        """Calculate ME supply using full NASEM model. Returns An_MEIn in Mcal/day."""
        result = self.calculate_values(feedbase, diet_composition, animal_input, ["An_MEIn"])
        return result.get("An_MEIn", 0.0)
    



# Singleton
_nasem_service: Optional[NASEMService] = None

def get_nasem_service() -> NASEMService:
    """Get or create NASEMService singleton."""
    global _nasem_service
    if _nasem_service is None:
        _nasem_service = NASEMService()
    return _nasem_service
