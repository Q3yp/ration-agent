#!/usr/bin/env python3
"""
Database migration to initialize 'token_stats' in user_sessions metadata.
This migration updates the metadata JSONB column to include token_stats
with default values (all zeros) for existing sessions that don't have it.
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
    """Run the migration to initialize token_stats in user_sessions metadata"""

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
                print("Starting migration: initialize token_stats in sessions metadata...")

                # Check how many sessions are missing token_stats
                await cur.execute("""
                    SELECT COUNT(*)
                    FROM user_sessions
                    WHERE metadata IS NULL
                       OR NOT (metadata ? 'token_stats')
                """)

                sessions_to_update = (await cur.fetchone())[0]
                print(f"Found {sessions_to_update} sessions without token_stats")

                if sessions_to_update == 0:
                    print("Migration completed - all sessions already have token_stats")
                    return

                # Update existing sessions to add token_stats with default values
                await cur.execute("""
                    UPDATE user_sessions
                    SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb),
                        '{token_stats}',
                        '{"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}'::jsonb
                    )
                    WHERE metadata IS NULL
                       OR NOT (metadata ? 'token_stats')
                """)

                rows_updated = cur.rowcount
                print(f"Updated {rows_updated} sessions with default token_stats")

                # Verify migration
                await cur.execute("""
                    SELECT COUNT(*)
                    FROM user_sessions
                    WHERE metadata IS NULL
                       OR NOT (metadata ? 'token_stats')
                """)

                remaining_null_count = (await cur.fetchone())[0]
                if remaining_null_count > 0:
                    print(f"Warning: {remaining_null_count} sessions still missing token_stats")
                else:
                    print("Migration completed successfully - all sessions have token_stats")

                # Show sample of migrated data
                await cur.execute("""
                    SELECT session_id, metadata->'token_stats' as token_stats
                    FROM user_sessions
                    LIMIT 3
                """)

                print("\nSample migrated sessions:")
                rows = await cur.fetchall()
                for row in rows:
                    print(f"  Session {row[0]}: {row[1]}")

    except Exception as e:
        print(f"Migration failed: {e}")
        raise
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
