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
        print("✅ Connected to database")
        
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
                    print("⚠️  Column 'deleted' already exists in user_sessions table")
                    return
                
                # Add the deleted column with default value FALSE
                print("🔄 Adding 'deleted' column to user_sessions table...")
                await cur.execute("""
                    ALTER TABLE user_sessions 
                    ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT FALSE
                """)
                
                print("✅ Successfully added 'deleted' column to user_sessions table")
                
                # Verify the column was added
                await cur.execute("""
                    SELECT column_name, data_type, column_default 
                    FROM information_schema.columns 
                    WHERE table_name = 'user_sessions' 
                    AND column_name = 'deleted'
                """)
                
                result = await cur.fetchone()
                if result:
                    print(f"✅ Verified column: {result[0]} ({result[1]}) with default: {result[2]}")
                else:
                    print("❌ Failed to verify column addition")
                    
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await pool.close()
        print("🔌 Database connection closed")


if __name__ == "__main__":
    print("🚀 Running migration: Add deleted column to user_sessions table")
    asyncio.run(run_migration())
    print("✅ Migration completed")
