#!/usr/bin/env python3
"""
Database migration to add (or ensure) an account tier column and remove any
legacy pets_enabled column from the users table. Existing accounts default to
the free tier. The script is idempotent and safe to re-run.
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


async def column_exists(cursor, column_name: str) -> bool:
    await cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = %s
        """,
        (column_name,),
    )
    return await cursor.fetchone() is not None


async def run_migration():
    """Add tier column to users if missing and drop pets_enabled if present."""
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
                print("Starting migration: ensure tier column and drop pets_enabled...")

                if not await column_exists(cur, "tier"):
                    await cur.execute(
                        """
                        ALTER TABLE "users"
                        ADD COLUMN tier VARCHAR(20) NOT NULL DEFAULT 'free'
                        """
                    )
                    print("✓ Added tier column (default 'free').")
                else:
                    print("Tier column already exists, skipping.")

                if await column_exists(cur, "pets_enabled"):
                    await cur.execute(
                        """
                        ALTER TABLE "users"
                        DROP COLUMN pets_enabled
                        """
                    )
                    print("✓ Removed legacy pets_enabled column.")
                else:
                    print("pets_enabled column not found, nothing to remove.")

                await cur.execute(
                    """
                    UPDATE "users"
                    SET allowed_animal_types = '["cat","dog"]'::json
                    WHERE (allowed_animal_types IS NULL OR allowed_animal_types::jsonb = '[]'::jsonb)
                      AND tier = 'free'
                    """
                )
                print("✓ Ensured free-tier users default to cat/dog access.")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
