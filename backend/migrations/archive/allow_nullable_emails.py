#!/usr/bin/env python3
"""
Migration to allow NULL values in users.email so non-email accounts can be created.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

load_dotenv()


def _db_uri() -> str:
    return (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )


async def run_migration():
    uri = _db_uri()
    pool = AsyncConnectionPool(
        uri,
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
                print("Dropping NOT NULL constraint on users.email (if present)...")
                await cur.execute(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_name = 'users'
                              AND column_name = 'email'
                              AND is_nullable = 'NO'
                        ) THEN
                            ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
                        END IF;
                    END;
                    $$;
                    """
                )
                print("users.email is now nullable.")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
