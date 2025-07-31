#!/usr/bin/env python3
"""
Database migration to add 'deleted' column to user_sessions table.
This migration adds a boolean 'deleted' column with default value FALSE
to support soft delete functionality for sessions.
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
    """Run the migration to add deleted column to user_sessions table"""
    
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
                # Check if the deleted column already exists
                await cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'user_sessions' 
                    AND column_name = 'deleted'
                """)
                
                existing_column = await cur.fetchone()
                
                if existing_column:
                    return
                
                # Add the deleted column with default value FALSE
                await cur.execute("""
                    ALTER TABLE user_sessions 
                    ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT FALSE
                """)
                
                
                # Verify the column was added
                await cur.execute("""
                    SELECT column_name, data_type, column_default 
                    FROM information_schema.columns 
                    WHERE table_name = 'user_sessions' 
                    AND column_name = 'deleted'
                """)
                
                result = await cur.fetchone()
                if not result:
                    raise Exception("Failed to verify column addition")
                    
    except Exception as e:
        raise
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
