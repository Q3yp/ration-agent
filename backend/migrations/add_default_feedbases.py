"""Migration: populate system default feedbases from a single consolidated JSON file."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure backend package is importable when the migration is executed
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Load environment variables so the store layer can connect
load_dotenv(BACKEND_ROOT / ".env")

from utils.system_feedbases import (
    SYSTEM_FEEDBASES_PATH,
    get_system_feedbases,
    list_system_feedbase_names,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migration() -> None:
    """Store every default feedbase defined in the consolidated JSON file."""

    logger.info("Starting default feedbase migration from %s", SYSTEM_FEEDBASES_PATH)
    feedbases = get_system_feedbases()
    if not feedbases:
        raise RuntimeError(
            f"No feedbases found in {SYSTEM_FEEDBASES_PATH}. The file must define at least one entry."
        )

    from core.agent import _connection_manager

    store = await _connection_manager.get_shared_store()

    for name, feedbase in feedbases.items():
        namespace = ("system_feedbases", name)
        await store.aput(namespace, "data", feedbase)
        logger.info(
            "\u2713 Stored %s (%s feeds for %s)",
            name,
            len(feedbase.get("feeds", {})),
            feedbase.get("animal_type"),
        )

    logger.info("Migration completed. System feedbases available: %s", ", ".join(list_system_feedbase_names()))


if __name__ == "__main__":
    asyncio.run(run_migration())
