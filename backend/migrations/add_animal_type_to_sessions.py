#!/usr/bin/env python3
"""
Database migration to add 'animal_type' to user_sessions metadata.
This migration updates the metadata JSONB column to include animal_type
with default value 'dairy_cow' for existing sessions.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def run_migration():
    """Run the migration to add animal_type to user_sessions metadata"""

    # Database connection parameters
    db_uri = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": None,
    }

    # Create connection pool
    pool = AsyncConnectionPool(
        db_uri,
        kwargs=connection_kwargs,
        min_size=1,
        max_size=5,
        timeout=10.0,
        open=False
    )

    try:
        await pool.open()

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                print("Starting migration: add animal_type to sessions metadata...")

                # Update existing sessions to add animal_type = 'dairy_cow' to metadata
                await cur.execute("""
                    UPDATE user_sessions
                    SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb),
                        '{animal_type}',
                        '"dairy_cow"'
                    )
                    WHERE metadata IS NULL
                       OR NOT (metadata ? 'animal_type')
                """)

                rows_updated = cur.rowcount
                print(f"Updated {rows_updated} sessions with default animal_type='dairy_cow'")

                # Verify migration
                await cur.execute("""
                    SELECT COUNT(*)
                    FROM user_sessions
                    WHERE metadata->>'animal_type' IS NULL
                """)

                null_count = (await cur.fetchone())[0]
                if null_count > 0:
                    print(f"Warning: {null_count} sessions still have null animal_type")
                else:
                    print("Migration completed successfully - all sessions have animal_type")

    except Exception as e:
        print(f"Migration failed: {e}")
        raise
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
