#!/usr/bin/env python3
"""
Database migration to add phone_number column to users and create sms_verifications table.
Run once after deploying the SMS registration feature.
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


def _build_db_uri() -> str:
    return (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )


async def run_migration():
    """Apply schema changes for SMS registration support."""
    db_uri = _build_db_uri()
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
                print("Ensuring pgcrypto extension exists...")
                await cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

                print("Checking for phone_number column on users...")
                await cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'phone_number'
                    """
                )
                if not await cur.fetchone():
                    print("Adding phone_number column to users...")
                    await cur.execute(
                        """
                        ALTER TABLE "users"
                        ADD COLUMN phone_number VARCHAR(20) UNIQUE
                        """
                    )
                else:
                    print("phone_number column already exists. Skipping.")

                print("Creating sms_verifications table if missing...")
                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sms_verifications (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        mobile VARCHAR(20) NOT NULL,
                        code_hash VARCHAR(255) NOT NULL,
                        purpose VARCHAR(32) NOT NULL DEFAULT 'register',
                        template_id VARCHAR(32),
                        expires_at TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        verified_at TIMESTAMPTZ,
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        user_id UUID REFERENCES users(id) ON DELETE SET NULL
                    )
                    """
                )

                print("Ensuring indexes on sms_verifications...")
                await cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sms_verifications_mobile
                    ON sms_verifications(mobile)
                    """
                )
                await cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sms_verifications_expires_at
                    ON sms_verifications(expires_at)
                    """
                )

                print("Migration completed successfully.")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
