#!/usr/bin/env python3
"""
Database migration to add stop_requested column to sessions table
Run this script to update your database schema
"""
import os
import asyncio
from psycopg_pool import AsyncConnectionPool


async def add_stop_requested_column():
    """Add stop_requested column to sessions table"""
    
    # Database connection details
    db_uri = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": None,
    }
    
    pool = AsyncConnectionPool(
        db_uri,
        kwargs=connection_kwargs,
        min_size=1,
        max_size=3,
        timeout=10.0
    )
    
    try:
        await pool.open()
        
        async with pool.connection() as conn:
            # Check if column already exists
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'user_sessions' 
                        AND column_name = 'stop_requested'
                    )
                """)
                exists = (await cur.fetchone())[0]
                
                if not exists:
                    print("Adding stop_requested column to user_sessions table...")
                    await cur.execute("""
                        ALTER TABLE user_sessions 
                        ADD COLUMN stop_requested BOOLEAN DEFAULT FALSE
                    """)
                    print("✅ Successfully added stop_requested column")
                else:
                    print("ℹ️ stop_requested column already exists")
    
    except Exception as e:
        print(f"❌ Error adding stop_requested column: {e}")
        raise
    
    finally:
        await pool.close()


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    asyncio.run(add_stop_requested_column())