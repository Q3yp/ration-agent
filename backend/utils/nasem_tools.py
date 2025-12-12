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
async def calculate_dairy_requirements(
    feedbase_name: str,
    body_weight_kg: float,
    days_in_milk: int,
    parity: int,
    target_milk_kg: float,
    reference_diet: Optional[Dict[str, float]] = None,
    milk_fat_percent: float = 3.5,
    milk_protein_percent: float = 3.2,
    days_pregnant: int = 0,
    breed: str = "Holstein",
    target_dmi_kg: Optional[float] = None,
    state: Annotated[dict, InjectedState] = None,
    config: RunnableConfig = None
) -> str:
    """Calculate NASEM nutrient requirements for a dairy cow.
    
    Use this tool to get NASEM 2021 requirements before formulation.
    No need to specify feeds - a reference diet is auto-selected if not provided.
    
    Args:
        feedbase_name: Name of feedbase to use (e.g., "default_dairy_cow")
        body_weight_kg: Animal body weight in kg
        days_in_milk: Days since calving (DIM)
        parity: Number of lactations (1 = first calf heifer)
        target_milk_kg: Target milk production in kg/day
        reference_diet: OPTIONAL - Dict of {feed_key: kg_dm_per_day}. 
                       If omitted, auto-selects common feeds from feedbase
                       (corn silage, alfalfa, soybean meal, corn grain)
        milk_fat_percent: Target milk fat percentage (default 3.5)
        milk_protein_percent: Target milk protein percentage (default 3.2)
        days_pregnant: Days of gestation (default 0)
        breed: "Holstein", "Jersey", or "Other"
        target_dmi_kg: Optional target DMI, estimated if not provided
    
    Returns:
        JSON with NASEM predictions including:
        - predicted_milk_kg: Actual milk limited by MP or NE
        - limiting_factor: "MP (protein)", "NE (energy)", or "balanced"
        - mp_allowable_milk_kg, ne_allowable_milk_kg: Milk allowed by each nutrient
        - me_intake_mcal, me_required_mcal: Energy balance
        - mp_intake_g, mp_required_g, rdp_intake_g: Protein balance
        - dmi_kg, lys_percent_mp, met_percent_mp, dcad_meq
    """
    try:
        user_id = config["configurable"].get("user_id") if config else None
        if not user_id:
            return json.dumps({"status": "error", "error": "User ID not found"})
        
        # Load feedbase
        feedbase = await _get_feedbase(user_id, feedbase_name)
        if not feedbase:
            return json.dumps({"status": "error", "error": f"Feedbase '{feedbase_name}' not found"})
        
        # Auto-select reference diet if not provided
        if not reference_diet:
            estimated_dmi = target_dmi_kg if target_dmi_kg else (body_weight_kg * 0.035 + target_milk_kg * 0.1)
            reference_diet = _build_default_reference_diet(feedbase, estimated_dmi)
            if not reference_diet:
                return json.dumps({"status": "error", "error": "Could not build default reference diet from feedbase"})
        
        service = get_nasem_service()
        
        # Build animal input
        animal_input = service.build_animal_input(
            body_weight_kg=body_weight_kg,
            days_in_milk=days_in_milk,
            parity=parity,
            target_milk_kg=target_milk_kg,
            milk_fat_percent=milk_fat_percent,
            milk_protein_percent=milk_protein_percent,
            days_pregnant=days_pregnant,
            breed=breed,
            target_dmi_kg=target_dmi_kg
        )
        
        # Calculate requirements
        result = service.calculate_requirements(
            feedbase=feedbase,
            reference_diet=reference_diet,
            animal_input=animal_input
        )
        
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in calculate_dairy_requirements: {e}")
        return json.dumps({"status": "error", "error": str(e)})


@tool
async def evaluate_diet_with_nasem(
    feedbase_name: str,
    diet_composition: Dict[str, float],
    body_weight_kg: float,
    days_in_milk: int,
    parity: int,
    target_milk_kg: float,
    milk_fat_percent: float = 3.5,
    milk_protein_percent: float = 3.2,
    days_pregnant: int = 0,
    breed: str = "Holstein",
    state: Annotated[dict, InjectedState] = None,
    config: RunnableConfig = None
) -> str:
    """Evaluate a formulated diet using the NASEM dairy model.
    
    Use this AFTER formulation to predict actual cow performance.
    
    Args:
        feedbase_name: Name of feedbase containing the diet feeds
        diet_composition: Dict of {feed_key: kg_dm_per_day} from formulation
        body_weight_kg: Animal body weight in kg
        days_in_milk: Days since calving
        parity: Number of lactations
        target_milk_kg: Target milk production for comparison
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
        - diet_summary: {total_dmi_kg, feed_count}
    """
    try:
        user_id = config["configurable"].get("user_id") if config else None
        if not user_id:
            return json.dumps({"status": "error", "error": "User ID not found"})
        
        # Load feedbase
        feedbase = await _get_feedbase(user_id, feedbase_name)
        if not feedbase:
            return json.dumps({"status": "error", "error": f"Feedbase '{feedbase_name}' not found"})
        
        service = get_nasem_service()
        
        # Build animal input
        animal_input = service.build_animal_input(
            body_weight_kg=body_weight_kg,
            days_in_milk=days_in_milk,
            parity=parity,
            target_milk_kg=target_milk_kg,
            milk_fat_percent=milk_fat_percent,
            milk_protein_percent=milk_protein_percent,
            days_pregnant=days_pregnant,
            breed=breed
        )
        
        # Evaluate diet
        result = service.evaluate_diet(
            feedbase=feedbase,
            diet_composition=diet_composition,
            animal_input=animal_input
        )
        
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error in evaluate_diet_with_nasem: {e}")
        return json.dumps({"status": "error", "error": str(e)})


def get_nasem_tools():
    """Return the list of NASEM tools for agent registration."""
    return [
        calculate_dairy_requirements,
        evaluate_diet_with_nasem
    ]
