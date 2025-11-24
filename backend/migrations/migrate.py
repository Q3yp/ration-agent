#!/usr/bin/env python3
"""
Unified migration script for Ration Agent.
Runs database schema updates and seeds initial data.
"""
import asyncio
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend package is importable
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from migrations.schema_manager import SchemaManager
from utils.system_feedbases import get_system_feedbases, list_system_feedbase_names

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    
    logger.info("=== Starting Ration Agent Migration ===")
    
    manager = SchemaManager()
    
    # 1. Update SQL Schema
    logger.info("--- Phase 1: SQL Schema Updates ---")
    await manager.update_schema()
    
    # 2. Seed Data
    logger.info("--- Phase 2: Data Seeding ---")
    await manager.seed_feedbases()
    
    logger.info("=== Migration Completed Successfully ===")

if __name__ == "__main__":
    asyncio.run(main())
