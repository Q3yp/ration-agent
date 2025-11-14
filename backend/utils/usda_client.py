"""USDA FoodData Central client helpers.

Provides a thin wrapper around the FoodData Central API so it can be reused
across CLI scripts and LangGraph tools without duplicating request logic.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    # Try loading backend/.env explicitly so CLI scripts and tools work even when
    # the environment wasn't pre-populated by the caller.
    backend_root = Path(__file__).resolve().parent.parent
    env_path = backend_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

    _ENV_LOADED = True


class USDAClient:
    """Small helper for querying the FoodData Central API."""

    BASE_URL = "https://api.nal.usda.gov/fdc/v1"

    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        _ensure_env_loaded()
        self.api_key = api_key or os.getenv("USDA_API_KEY")
        if not self.api_key:
            raise ValueError("USDA_API_KEY is not configured in the environment")

        if session is None:
            session = requests.Session()
            retry = Retry(
                total=5,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET", "POST"),
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("https://", adapter)
            session.mount("http://", adapter)

        self._session = session

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Execute a request against the API and return parsed JSON."""

        params = params.copy() if params else {}
        params["api_key"] = self.api_key
        url = f"{self.BASE_URL}/{path.lstrip('/')}"

        response = self._session.request(method, url, params=params, timeout=kwargs.pop("timeout", 30), **kwargs)
        response.raise_for_status()
        return response.json()

    def search_foods(
        self,
        query: str,
        *,
        data_type: Optional[List[str]] = None,
        page_size: int = 25,
        page_number: int = 1,
        require_all_words: bool = True,
        nutrient_ids: Optional[List[int]] = None,
        general_search_input: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for foods and return the raw API payload."""

        payload: Dict[str, Any] = {
            "query": query,
            "pageSize": max(1, min(page_size, 200)),
            "pageNumber": max(1, page_number),
            "requireAllWords": require_all_words,
        }

        if data_type:
            payload["dataType"] = data_type

        if nutrient_ids:
            payload["nutrientIds"] = nutrient_ids

        if general_search_input:
            payload["generalSearchInput"] = general_search_input

        logger.info("Searching USDA foods for query '%s'", query)
        return self._request("post", "foods/search", json=payload)

    def get_food(self, fdc_id: int) -> Dict[str, Any]:
        """Fetch detailed nutrient info for an FDC ID."""

        logger.info("Fetching USDA food details for FDC ID %s", fdc_id)
        return self._request("get", f"food/{fdc_id}")


def format_nutrients(nutrients: List[Dict[str, Any]], wanted_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Return a compact nutrient list filtered by friendly names if provided."""

    if not nutrients:
        return []

    if wanted_names:
        lowered = {name.lower() for name in wanted_names}
        filtered = [n for n in nutrients if n.get("nutrientName", "").lower() in lowered]
    else:
        filtered = nutrients

    simplified = []
    for nutrient in filtered:
        simplified.append(
            {
                "name": nutrient.get("nutrientName"),
                "amount": nutrient.get("value"),
                "unit": nutrient.get("unitName"),
            }
        )

    return simplified
