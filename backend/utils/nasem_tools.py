"""NASEM Dairy Model Tools for Agent Integration.

Provides LangChain tools for the NASEM 2021 Dairy Cattle Model.
Tools load feedbase from store and pass to NASEMService.
"""

import json
import logging
from typing import Annotated, Optional, Dict, Any

from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store

from services.nasem_service import get_nasem_service

logger = logging.getLogger(__name__)

# Default reference diet feed patterns based on NASEM demo examples
# Priority order: more specific patterns first
DEFAULT_DIET_PATTERNS = [
    # (pattern, target_kg_dm, category_hint)
    ("corn_silage", 8.0, "forage"),
    ("alfalfa", 5.0, "forage"),  
    ("soybean_meal", 3.0, "protein"),
    ("corn_grain", 4.0, "grain"),
]


def _build_default_reference_diet(feedbase: Dict[str, Any], target_dmi_kg: float = 24.0) -> Dict[str, float]:
    """Build a default reference diet from feedbase using common feed patterns.
    
    Tries to find feeds matching NASEM demo patterns and scales to target DMI.
    
    Args:
        feedbase: Feedbase dict with {"feeds": {...}}
        target_dmi_kg: Target total DMI (default 24 kg/day for lactating cow)
    
    Returns:
        Dict of {feed_key: kg_dm_per_day}
    """
    feeds = feedbase.get("feeds", {})
    if not feeds:
        return {}
    
    selected = {}
    total_planned = sum(p[1] for p in DEFAULT_DIET_PATTERNS)
    
    for pattern, base_kg, category in DEFAULT_DIET_PATTERNS:
        # Find first matching feed
        for feed_key, feed_data in feeds.items():
            if pattern in feed_key.lower():
                # Scale to target DMI
                scaled_kg = base_kg * (target_dmi_kg / total_planned)
                selected[feed_key] = round(scaled_kg, 2)
                break
    
    # If we found less than 2 feeds, just pick first 4 feeds from feedbase
    if len(selected) < 2:
        logger.warning("Could not match default diet patterns, using first available feeds")
        selected = {}
        feed_keys = list(feeds.keys())[:4]
        if feed_keys:
            per_feed_kg = target_dmi_kg / len(feed_keys)
            for key in feed_keys:
                selected[key] = round(per_feed_kg, 2)
    
    logger.info(f"Auto-selected reference diet: {selected}")
    return selected


async def _get_feedbase(user_id: str, feedbase_name: str) -> Optional[Dict[str, Any]]:
    """Load feedbase from store."""
    store = get_store()
    
    # Try user feedbase first
    namespace = ("feedbases", user_id, feedbase_name)
    result = await store.aget(namespace, "data")
    if result:
        return result.value
    
    # Try system feedbase
    namespace = ("system_feedbases", feedbase_name)
    result = await store.aget(namespace, "data")
    if result:
        return result.value
    
    return None


@tool
async def predict_dairy_requirements(
    body_weight_kg: Optional[float] = None,
    days_in_milk: Optional[int] = None,
    parity: Optional[int] = None,
    target_milk_kg: Optional[float] = None,
    milk_fat_percent: Optional[float] = None,
    milk_protein_percent: Optional[float] = None,
    body_condition_score: Optional[float] = None,
    days_pregnant: Optional[int] = None,
    breed: Optional[str] = None,
    state: Annotated[dict, InjectedState] = None,
    config: RunnableConfig = None
) -> str:
    """Predict NASEM nutrient requirements for a dairy cow based on animal parameters.
    
    This tool calculates factorial requirements WITHOUT needing a diet. Use this to 
    get NASEM 2021 requirements BEFORE formulation. The predicted values are derived
    from animal parameters only using NASEM equations:
    
    - DMI prediction: Uses NASEM equation 8 (Lact1) - animal factors only
    - NE requirements: Maintenance + milk production + gestation + reserves
    - MP requirements: Maintenance + milk protein + gestation + growth
    - Mineral requirements: Ca, P, Mg based on production level
    
    If animal parameters were previously set via set_animal_params, they will be used
    as defaults. Explicit parameters passed here will override stored values.
    
    Note: Actual DMI and nutrient supply depend on diet composition. Use 
    formulate_ration with animal_params to get optimized diet with predicted DMI,
    then evaluate_diet_with_nasem for final validation.
    
    Args:
        body_weight_kg: Animal body weight in kg (uses stored value if not provided)
        days_in_milk: Days since calving (DIM) (uses stored value if not provided)
        parity: Number of lactations (1 = first calf heifer) (uses stored value if not provided)
        target_milk_kg: Target milk production in kg/day (uses stored value if not provided)
        milk_fat_percent: Target milk fat percentage (default 3.5)
        milk_protein_percent: Target milk protein percentage (default 3.2)
        body_condition_score: BCS on 1-5 scale (default 3.0)
        days_pregnant: Days of gestation (default 0)
        breed: "Holstein", "Jersey", or "Other"
    
    Returns:
        JSON with factorial requirements:
        - predicted_dmi_kg: Predicted DMI (animal-only, equation 8)
        - ne_required_mcal: Total NE requirement (maintenance + milk + gestation)
        - me_required_mcal: Total ME requirement (NE/0.64)
        - mp_required_g: Total MP requirement (g/day)
        - ca_required_g, p_required_g, mg_required_g: Mineral requirements
        - target_lys_percent_mp, target_met_percent_mp: Amino acid targets
        - formulation_constraints: Ready-to-use constraints for formulate_ration
    """
    import math
    
    try:
        # Get stored animal params from state as fallback
        stored_params = state.get("animal_params", {}) if state else {}
        
        # Resolve parameters: explicit > stored > defaults
        body_weight_kg = body_weight_kg if body_weight_kg is not None else stored_params.get("body_weight")
        days_in_milk = days_in_milk if days_in_milk is not None else stored_params.get("dim")
        parity = parity if parity is not None else stored_params.get("parity")
        target_milk_kg = target_milk_kg if target_milk_kg is not None else stored_params.get("milk_prod")
        milk_fat_percent = milk_fat_percent if milk_fat_percent is not None else stored_params.get("milk_fat_pct", 3.5)
        milk_protein_percent = milk_protein_percent if milk_protein_percent is not None else stored_params.get("milk_protein_pct", 3.2)
        body_condition_score = body_condition_score if body_condition_score is not None else stored_params.get("bcs", 3.0)
        days_pregnant = days_pregnant if days_pregnant is not None else stored_params.get("days_pregnant", 0)
        breed = breed if breed is not None else stored_params.get("breed", "Holstein")
        
        # Check required parameters
        if body_weight_kg is None or days_in_milk is None or parity is None or target_milk_kg is None:
            missing = []
            if body_weight_kg is None: missing.append("body_weight_kg")
            if days_in_milk is None: missing.append("days_in_milk")
            if parity is None: missing.append("parity")
            if target_milk_kg is None: missing.append("target_milk_kg")
            return json.dumps({
                "status": "error",
                "error": f"Missing required parameters: {', '.join(missing)}. Either provide them explicitly or use set_animal_params first."
            })
        
        # === DMI Prediction (NASEM Equation 8 - Lact1) ===
        # DMI = (3.7 + 5.7*(parity-1) + 0.305*NE_milk + 0.022*BW 
        #        + (-0.689 - 1.87*(parity-1))*BCS) 
        #       * (1 - (0.212 + 0.136*(parity-1)) * exp(-0.053*DIM))
        
        # Calculate NE of milk (Mcal/kg)
        milk_lac_pct = 4.85  # Standard lactose
        ne_milk_per_kg = 0.0929 * milk_fat_percent + 0.0547 * milk_protein_percent + 0.0395 * milk_lac_pct
        ne_milk_output = ne_milk_per_kg * target_milk_kg
        
        parity_adj = parity - 1
        parity_factor = min(parity_adj, 1)  # Cap at 1 for equation
        
        predicted_dmi = ((3.7 + 5.7 * parity_factor + 0.305 * ne_milk_output + 0.022 * body_weight_kg + 
                         (-0.689 - 1.87 * parity_factor) * body_condition_score) * 
                        (1 - (0.212 + 0.136 * parity_factor) * math.exp(-0.053 * days_in_milk)))
        predicted_dmi = max(predicted_dmi, 12.0)  # Minimum 12 kg for lactating cows
        
        # === NE Requirements ===
        # NE maintenance (Mcal/day) - NASEM approximation
        ne_maintenance = 0.08 * (body_weight_kg ** 0.75)
        
        # NE for milk
        ne_lactation = ne_milk_output
        
        # NE for gestation (if pregnant)
        ne_gestation = 0.0
        if days_pregnant > 190:
            # Exponential increase in late gestation
            ne_gestation = 0.00159 * math.exp(0.0231 * days_pregnant)
        
        ne_total = ne_maintenance + ne_lactation + ne_gestation
        
        # === MP Requirements ===
        # MP maintenance (g/day)
        # Scurf + endogenous urinary + fecal metabolic
        mp_maintenance = 4.1 * (body_weight_kg ** 0.75)
        
        # MP for milk protein (efficiency ~0.67)
        milk_protein_kg = target_milk_kg * (milk_protein_percent / 100)
        mp_lactation = (milk_protein_kg * 1000) / 0.67
        
        # MP for gestation
        mp_gestation = 0.0
        if days_pregnant > 190:
            mp_gestation = 0.69 * math.exp(0.0156 * days_pregnant)
        
        # MP for growth (heifers only)
        mp_growth = 0.0
        if parity == 1:
            # First lactation cows still growing
            mature_bw = body_weight_kg * 1.10  # Assume 10% growth to mature
            mp_growth = 30.0  # Approximate g/day for growing heifers
        
        mp_total = mp_maintenance + mp_lactation + mp_gestation + mp_growth
        
        # === Mineral Requirements ===
        # Calcium (g/day) - maintenance + milk
        ca_maintenance = 0.0154 * body_weight_kg
        ca_milk = target_milk_kg * 1.22  # ~1.22g Ca per kg milk
        ca_required = ca_maintenance + ca_milk
        
        # Phosphorus (g/day)
        p_maintenance = 0.0143 * body_weight_kg
        p_milk = target_milk_kg * 0.95  # ~0.95g P per kg milk
        p_required = p_maintenance + p_milk
        
        # Magnesium (g/day)
        mg_maintenance = 0.003 * body_weight_kg
        mg_milk = target_milk_kg * 0.15
        mg_required = mg_maintenance + mg_milk
        
        # === Amino Acid Targets ===
        target_lys_pct = 7.2  # % of MP
        target_met_pct = 2.5  # % of MP
        
        # === Build Formulation Constraints ===
        # These can be passed directly to formulate_ration
        me_required = ne_total / 0.64  # Approximate ME from NE (km~0.64)
        
        # Only include calculated constraints based on actual requirements
        # CP, NDF, ADF are not included - these should be set by the nutritionist
        # based on specific formulation goals, not auto-calculated
        formulation_constraints = [
            {"type": "concentration", "nutrient": "Fd_Ca", "min": round(ca_required / predicted_dmi / 10, 2)},  # g/kg DM / 10 = % DM
            {"type": "concentration", "nutrient": "Fd_P", "min": round(p_required / predicted_dmi / 10, 2)},   # g/kg DM / 10 = % DM
        ]
        
        result = {
            "status": "success",
            "animal_info": {
                "body_weight_kg": body_weight_kg,
                "days_in_milk": days_in_milk,
                "parity": parity,
                "target_milk_kg": target_milk_kg,
                "milk_fat_percent": milk_fat_percent,
                "milk_protein_percent": milk_protein_percent,
                "bcs": body_condition_score,
                "breed": breed
            },
            "requirements": {
                "predicted_dmi_kg": round(predicted_dmi, 1),
                "ne_required_mcal": round(ne_total, 1),
                "ne_maintenance_mcal": round(ne_maintenance, 1),
                "ne_lactation_mcal": round(ne_lactation, 1),
                "me_required_mcal": round(me_required, 1),
                "mp_required_g": round(mp_total, 0),
                "mp_maintenance_g": round(mp_maintenance, 0),
                "mp_lactation_g": round(mp_lactation, 0),
                "ca_required_g_per_day": round(ca_required, 1),
                "p_required_g_per_day": round(p_required, 1),
                "mg_required_g_per_day": round(mg_required, 1),
                "target_lys_percent_mp": target_lys_pct,
                "target_met_percent_mp": target_met_pct
            },
            "units": {
                "dmi": "kg/day",
                "ne": "Mcal/day",
                "mp": "g/day",
                "minerals (Ca, P, Mg)": "g/day",
                "amino_acids": "% of MP"
            },
            "formulation_constraints": formulation_constraints,
            "notes": [
                "DMI predicted using NASEM equation 8 (animal factors only)",
                "Actual DMI will vary based on diet NDF content",
                "Use formulate_ration with animal_params for diet-adjusted DMI",
                "Use evaluate_diet_with_nasem for final validation after formulation"
            ]
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in predict_dairy_requirements: {e}")
        return json.dumps({"status": "error", "error": str(e)})


@tool
async def evaluate_diet_with_nasem(
    body_weight_kg: Optional[float] = None,
    days_in_milk: Optional[int] = None,
    parity: Optional[int] = None,
    target_milk_kg: Optional[float] = None,
    milk_fat_percent: Optional[float] = None,
    milk_protein_percent: Optional[float] = None,
    days_pregnant: Optional[int] = None,
    breed: Optional[str] = None,
    state: Annotated[dict, InjectedState] = None,
    config: RunnableConfig = None
) -> str:
    """Evaluate the current formulated diet using the NASEM dairy model.
    
    IMPORTANT: You must have a successful formulation in state before calling this.
    This tool automatically uses the current formulation from state - do NOT 
    provide diet composition manually.
    
    If animal parameters were previously set via set_animal_params, they will be used
    as defaults. Explicit parameters passed here will override stored values.
    
    Use this AFTER formulate_ration to predict actual cow performance.
    
    Args:
        body_weight_kg: Animal body weight in kg (uses stored value if not provided)
        days_in_milk: Days since calving (uses stored value if not provided)
        parity: Number of lactations (uses stored value if not provided)
        target_milk_kg: Target milk production for comparison (uses stored value if not provided)
        milk_fat_percent: Target milk fat percentage
        milk_protein_percent: Target milk protein percentage
        days_pregnant: Days of gestation
        breed: "Holstein", "Jersey", or "Other"
    
    Returns:
        JSON with NASEM predictions including:
        - predicted_milk_kg: Actual milk limited by MP or NE
        - limiting_factor: "MP (protein)", "NE (energy)", or "balanced"
        - mp_allowable_milk_kg, ne_allowable_milk_kg: Milk allowed by each nutrient
        - me_intake_mcal, me_required_mcal: Energy balance
        - mp_intake_g, mp_required_g, rdp_intake_g: Protein balance
        - dmi_kg, lys_percent_mp, met_percent_mp, dcad_meq
        - diet_summary: {total_fresh_intake_kg, feed_count}
    """
    try:
        # Check for successful formulation in state
        current_formulation = state.get("current_formulation", {}) if state else {}
        if not current_formulation or current_formulation.get("status") != "success":
            return json.dumps({
                "status": "error", 
                "error": "No successful formulation found. Please run formulate_ration first."
            })
        
        # Get stored animal params from state as fallback
        stored_params = state.get("animal_params", {}) if state else {}
        
        # Resolve parameters: explicit > stored > defaults
        body_weight_kg = body_weight_kg if body_weight_kg is not None else stored_params.get("body_weight")
        days_in_milk = days_in_milk if days_in_milk is not None else stored_params.get("dim")
        parity = parity if parity is not None else stored_params.get("parity")
        target_milk_kg = target_milk_kg if target_milk_kg is not None else stored_params.get("milk_prod")
        milk_fat_percent = milk_fat_percent if milk_fat_percent is not None else stored_params.get("milk_fat_pct", 3.5)
        milk_protein_percent = milk_protein_percent if milk_protein_percent is not None else stored_params.get("milk_protein_pct", 3.2)
        days_pregnant = days_pregnant if days_pregnant is not None else stored_params.get("days_pregnant", 0)
        breed = breed if breed is not None else stored_params.get("breed", "Holstein")
        
        # Check required parameters
        if body_weight_kg is None or days_in_milk is None or parity is None or target_milk_kg is None:
            missing = []
            if body_weight_kg is None: missing.append("body_weight_kg")
            if days_in_milk is None: missing.append("days_in_milk")
            if parity is None: missing.append("parity")
            if target_milk_kg is None: missing.append("target_milk_kg")
            return json.dumps({
                "status": "error",
                "error": f"Missing required parameters: {', '.join(missing)}. Either provide them explicitly or use set_animal_params first."
            })
        
        # Get feedbase reference from state
        feedbase_name = state.get("current_feedbase_name", "")
        user_id = state.get("current_user_id", "")
        
        if not feedbase_name or not user_id:
            # Fallback to config for user_id
            user_id = config["configurable"].get("user_id") if config else None
            if not user_id:
                return json.dumps({"status": "error", "error": "User ID not found"})
            if not feedbase_name:
                return json.dumps({
                    "status": "error", 
                    "error": "Feedbase name not found in state. Please run formulate_ration first."
                })
        
        # Load feedbase
        feedbase = await _get_feedbase(user_id, feedbase_name)
        if not feedbase:
            return json.dumps({"status": "error", "error": f"Feedbase '{feedbase_name}' not found"})
        
        # Build diet composition using centralized helper (single source of truth)
        # This ensures diet composition and DMI are always consistent
        try:
            from services.nasem_service import NASEMService
            diet_composition, predicted_dmi_kg = NASEMService.build_diet_from_formulation(current_formulation)
        except ValueError as e:
            return json.dumps({"status": "error", "error": str(e)})
        
        service = get_nasem_service()
        
        # Build animal input using optimizer's predicted DMI
        animal_input = service.build_animal_input(
            body_weight_kg=body_weight_kg,
            days_in_milk=days_in_milk,
            parity=parity,
            target_milk_kg=target_milk_kg,
            milk_fat_percent=milk_fat_percent,
            milk_protein_percent=milk_protein_percent,
            days_pregnant=days_pregnant,
            breed=breed,
            target_dmi_kg=predicted_dmi_kg  # Use optimizer's DMI
        )
        
        # Evaluate diet
        result = service.evaluate_diet(
            feedbase=feedbase,
            diet_composition=diet_composition,
            animal_input=animal_input
        )
        
        # Add diet info to result for transparency
        if result.get("status") == "success":
            result["diet_used"] = diet_composition
            result["feedbase_used"] = feedbase_name
            
            # Check if predicted yields are constraint factors (>5% below target)
            warnings = []
            snapshot = result.get("snapshot", "")
            
            # Parse predicted milk values from snapshot
            import re
            mp_alow_match = re.search(r'Mlk_Prod_MPalow\):\s*([\d.]+)', snapshot)
            ne_alow_match = re.search(r'Mlk_Prod_NEalow\):\s*([\d.]+)', snapshot)
            pred_match = re.search(r'Mlk_Prod_comp\):\s*([\d.]+)', snapshot)
            
            threshold_pct = 5.0  # 5% threshold
            
            if mp_alow_match:
                mp_alow = float(mp_alow_match.group(1))
                deficit_pct = (target_milk_kg - mp_alow) / target_milk_kg * 100
                if deficit_pct > threshold_pct:
                    warnings.append(f"⚠️ MP (metabolizable protein) is limiting: MP-allowable milk = {mp_alow:.1f} kg is {deficit_pct:.1f}% below target {target_milk_kg:.1f} kg. Consider increasing RUP sources or rumen-protected amino acids.")
            
            if ne_alow_match:
                ne_alow = float(ne_alow_match.group(1))
                deficit_pct = (target_milk_kg - ne_alow) / target_milk_kg * 100
                if deficit_pct > threshold_pct:
                    warnings.append(f"⚠️ ME (metabolizable energy) is limiting: NE-allowable milk = {ne_alow:.1f} kg is {deficit_pct:.1f}% below target {target_milk_kg:.1f} kg. Consider increasing energy density with more grain or fat supplements.")
            
            if pred_match:
                pred = float(pred_match.group(1))
                deficit_pct = (target_milk_kg - pred) / target_milk_kg * 100
                if deficit_pct > threshold_pct:
                    warnings.append(f"⚠️ Predicted milk production = {pred:.1f} kg is {deficit_pct:.1f}% below target {target_milk_kg:.1f} kg. Review limiting factors above.")
            
            if warnings:
                result["yield_constraint_warnings"] = warnings
        
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in evaluate_diet_with_nasem: {e}")
        return json.dumps({"status": "error", "error": str(e)})


def get_nasem_tools():
    """Return the list of NASEM tools for agent registration."""
    return [
        predict_dairy_requirements,
        evaluate_diet_with_nasem
    ]

