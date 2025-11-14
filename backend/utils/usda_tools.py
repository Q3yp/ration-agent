"""LangGraph-compatible tools for interacting with the USDA FoodData API."""

from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.tools import tool

from .usda_client import USDAClient, format_nutrients

logger = logging.getLogger(__name__)


def _format_search_results(raw_results: dict, nutrient_names: Optional[List[str]]) -> str:
    foods = raw_results.get("foods", [])
    if not foods:
        return "No USDA foods were found for that query."

    lines = [f"Found {len(foods)} USDA matches:"]
    for food in foods:
        description = food.get("description", "Unnamed item")
        fdc_id = food.get("fdcId")
        data_type = food.get("dataType", "")
        source = food.get("foodCategory") or food.get("publicationDate") or ""
        nutrients = format_nutrients(food.get("foodNutrients") or [], nutrient_names)
        nutrient_summary = ", ".join(
            f"{n['name']}: {n['amount']} {n['unit']}" for n in nutrients
        )
        if not nutrient_summary:
            nutrient_summary = "(nutrients omitted in summary)"

        lines.append(f"- FDC {fdc_id} | {description} [{data_type}] {source}")
        lines.append(f"  Nutrients: {nutrient_summary}")

    return "\n".join(lines)


def _format_food_details(food: dict, nutrient_names: Optional[List[str]]) -> str:
    if not food:
        return "No details returned for that FDC ID."

    nutrients = format_nutrients(food.get("foodNutrients") or [], nutrient_names)
    nutrient_summary = "\n".join(
        f"  - {item['name']}: {item['amount']} {item['unit']}" for item in nutrients
    ) or "  (nutrients not available)"

    parts = [
        f"FDC ID: {food.get('fdcId')}",
        f"Description: {food.get('description')}",
        f"Data Type: {food.get('dataType')}",
        f"Publ. Date: {food.get('publicationDate', 'unknown')}",
        f"Food Category: {food.get('foodCategory')}",
        "Nutrients:",
        nutrient_summary,
    ]
    return "\n".join(parts)


@tool
def usda_search_foods(
    query: str,
    max_results: int = 10,
    data_sources: Optional[List[str]] = None,
    nutrient_names: Optional[List[str]] = None,
) -> str:
    """Query USDA FoodData Central for ingredients and return key nutrient info."""

    try:
        client = USDAClient()
        response = client.search_foods(
            query,
            data_type=data_sources,
            page_size=max_results,
        )
        return _format_search_results(response, nutrient_names)
    except Exception as exc:
        logger.exception("USDA search failed")
        return f"USDA search error: {exc}"


@tool
def usda_food_details(fdc_id: int, nutrient_names: Optional[List[str]] = None) -> str:
    """Fetch detailed nutrient info for a specific FDC ID."""

    try:
        client = USDAClient()
        data = client.get_food(fdc_id)
        return _format_food_details(data, nutrient_names)
    except Exception as exc:
        logger.exception("USDA detail lookup failed")
        return f"USDA food detail error: {exc}"


def get_usda_tools():
    """Expose USDA helper tools for agents."""

    return [usda_search_foods, usda_food_details]
