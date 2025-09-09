#!/usr/bin/env python3
"""
Manual setup script for LangGraph PostgresStore tables.
Run this once to initialize the store tables in the database.
"""

import asyncio
import os
from dotenv import load_dotenv
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg_pool import AsyncConnectionPool

# Load environment variables
load_dotenv()

async def setup_store():
    """Setup PostgresStore tables manually"""
    
    # Database connection details
    db_uri = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    print(f"Connecting to database: {os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}")
    
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
        # Open the pool
        await pool.open()
        print("✅ Database connection established")
        
        # Create store and setup tables
        store = AsyncPostgresStore(pool)
        print("🔧 Setting up store tables...")
        
        await store.setup()
        print("✅ Store tables created successfully!")
        
        # Test the store
        print("🧪 Testing store functionality...")
        test_namespace = ("test", "user1", "feedbase1")
        test_data = {"feeds": {"test_feed": {"dm_percent": 90.0}}}
        
        # Put test data
        await store.aput(test_namespace, "data", test_data)
        print("✅ Test data stored")
        
        # Get test data
        result = await store.aget(test_namespace, "data")
        if result and result.value == test_data:
            print("✅ Test data retrieved correctly")
        else:
            print("❌ Test data retrieval failed")
        
        # Clean up test data
        await store.adelete(test_namespace, "data")
        print("✅ Test data cleaned up")
        
        print("\n🎉 Store setup completed successfully!")
        print("The feedbase management system is ready to use.")
        
    except Exception as e:
        print(f"❌ Error setting up store: {e}")
        raise
    finally:
        if pool:
            await pool.close()
            print("🔐 Database connection closed")

if __name__ == "__main__":
    print("🚀 Starting LangGraph Store Setup...")
    asyncio.run(setup_store())