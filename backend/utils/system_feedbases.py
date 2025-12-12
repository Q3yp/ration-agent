from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict

SYSTEM_FEEDBASES_PATH = Path(__file__).resolve().parents[1] / "migrations" / "data" / "system_feedbases.json"

# NASEM feedbase with full Fd_* column names for dairy cow (extracted from NASEM feed library)
NASEM_FEEDBASE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "nasem_feedbase.json"


class SystemFeedbaseConfigError(RuntimeError):
    """Raised when the consolidated system feedbase JSON is missing or invalid."""


def _read_feedbase_file() -> Dict[str, dict]:
    if not SYSTEM_FEEDBASES_PATH.exists():
        raise SystemFeedbaseConfigError(
            f"System feedbase file not found at {SYSTEM_FEEDBASES_PATH}. Did you run the build script?"
        )

    try:
        with SYSTEM_FEEDBASES_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SystemFeedbaseConfigError(
            f"Failed to parse system feedbases JSON: {exc.msg}"
        ) from exc

    if not isinstance(data, dict):
        raise SystemFeedbaseConfigError("System feedbase JSON must be an object mapping names to feedbases")

    # Override dairy_cow with NASEM feedbase (full Fd_* columns for NASEM model compatibility)
    if NASEM_FEEDBASE_PATH.exists():
        try:
            with NASEM_FEEDBASE_PATH.open("r", encoding="utf-8") as fh:
                nasem_data = json.load(fh)
            if "default_dairy_cow_nasem" in nasem_data:
                # Use NASEM feedbase for dairy_cow (rename key to match expected format)
                data["default_dairy_cow"] = nasem_data["default_dairy_cow_nasem"]
                data["default_dairy_cow"]["animal_type"] = "dairy_cow"
        except (json.JSONDecodeError, IOError) as exc:
            # Fall back to regular feedbase if NASEM file has issues
            pass

    return data


@lru_cache(maxsize=1)
def _cached_feedbases() -> Dict[str, dict]:
    return _read_feedbase_file()


def reload_system_feedbases() -> None:
    """Clear the internal JSON cache so subsequent calls re-read from disk."""

    _cached_feedbases.cache_clear()  # type: ignore[attr-defined]


def get_system_feedbases() -> Dict[str, dict]:
    """Return a deep copy of all default system feedbases keyed by namespace."""

    feedbases = {}
    for name, payload in _cached_feedbases().items():
        if not isinstance(payload, dict):
            raise SystemFeedbaseConfigError(f"Feedbase entry '{name}' must be a JSON object")

        feedbase_copy = copy.deepcopy(payload)
        feedbase_copy.setdefault("animal_type", name.replace("default_", ""))
        feedbase_copy.setdefault("feeds", {})
        feedbase_copy.setdefault("feed_labels", {})
        feedbases[name] = feedbase_copy

    return feedbases


def list_system_feedbase_names() -> list[str]:
    """Return the available system feedbase names in deterministic order."""

    return sorted(get_system_feedbases().keys())


def get_system_feedbase(name: str) -> dict | None:
    """Return a single system feedbase definition if present."""

    return get_system_feedbases().get(name)
