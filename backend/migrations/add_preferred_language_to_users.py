#!/usr/bin/env python3
"""
Database migration to add 'preferred_language' column to the users table.
All existing users will default to zh-CN.
"""

import asyncio
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv

load_dotenv()


async def run_migration():
    """Add preferred_language column if it does not exist."""
    db_uri = (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )

    pool = AsyncConnectionPool(
        db_uri,
        kwargs={"autocommit": True, "prepare_threshold": None},
        min_size=1,
        max_size=5,
        timeout=10.0,
        open=False,
    )

    try:
        await pool.open()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                print("Starting migration: add preferred_language to users...")

                await cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'preferred_language'
                    """
                )
                if await cur.fetchone():
                    print("Column preferred_language already exists. Skipping.")
                    return

                await cur.execute(
                    """
                    ALTER TABLE "users"
                    ADD COLUMN preferred_language VARCHAR(10) NOT NULL DEFAULT 'zh-CN'
                    """
                )
                print("Added preferred_language column with default zh-CN.")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
