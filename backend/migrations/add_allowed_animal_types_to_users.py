#!/usr/bin/env python3
"""
Database migration to add 'allowed_animal_types' column to user table.
This migration adds a JSON column for storing user's allowed animal types
and sets all existing users to have access to all types by default (null = all allowed).
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
    """Run the migration to add allowed_animal_types column to user table"""

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
                print("Starting migration: add allowed_animal_types to user table...")

                # Check if the column already exists
                await cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users'
                    AND column_name = 'allowed_animal_types'
                """)

                existing_column = await cur.fetchone()

                if existing_column:
                    print("Column 'allowed_animal_types' already exists, skipping migration")
                    return

                # Add the allowed_animal_types column (nullable JSON)
                await cur.execute("""
                    ALTER TABLE "users"
                    ADD COLUMN allowed_animal_types JSON NULL
                """)

                print("Added 'allowed_animal_types' column to user table")

                # Note: We intentionally leave existing users with NULL
                # NULL means "all animal types allowed" (no restrictions)
                print("Existing users set to NULL (= all animal types allowed)")

                # Verify the column was added
                await cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'users'
                    AND column_name = 'allowed_animal_types'
                """)

                result = await cur.fetchone()
                if not result:
                    raise Exception("Failed to verify column addition")

                print(f"Migration completed successfully: {result}")

    except Exception as e:
        print(f"Migration failed: {e}")
        raise
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
