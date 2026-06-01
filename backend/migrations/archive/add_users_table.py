"""
Database migration to add users table and update sessions table
Run this after adding FastAPI-Users dependencies
"""
import asyncio
import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text, Boolean, DateTime, String, UUID, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://ration_user:ration_password@localhost:5433/ration_agent"

# Convert to async URL if needed
if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

async def run_migration():
    """Run the users table migration"""
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # Ensure required extensions exist
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        # Create users table (ensure timestamps have defaults)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(320) UNIQUE NOT NULL,
                username VARCHAR(100) UNIQUE NOT NULL,
                hashed_password VARCHAR(1024) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                is_superuser BOOLEAN DEFAULT FALSE,
                is_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                full_name VARCHAR(200),
                role VARCHAR(50) DEFAULT 'user'
            );
        """))

        # Ensure defaults exist if columns already present without defaults
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='created_at'
                ) THEN
                    EXECUTE 'ALTER TABLE users ALTER COLUMN created_at SET DEFAULT NOW()';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='updated_at'
                ) THEN
                    EXECUTE 'ALTER TABLE users ALTER COLUMN updated_at SET DEFAULT NOW()';
                END IF;
            END$$;
        """))
        
        # Create indexes for better performance
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);"))
        
        # Create user_sessions table for our session management
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id VARCHAR(255) PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                workspace_path TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                last_accessed TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                deleted BOOLEAN NOT NULL DEFAULT FALSE,
                metadata JSONB DEFAULT '{}'::jsonb
            );
        """))
        
        # Create indexes for user_sessions table
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_active_deleted ON user_sessions(active, deleted);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_last_accessed ON user_sessions(last_accessed);"))
        
        print("Created user_sessions table with indexes")
            
        # Create a default admin user if none exists
        admin_result = await conn.execute(text("""
            SELECT COUNT(*) FROM users WHERE is_superuser = TRUE;
        """))
        
        admin_count = admin_result.scalar()
        
        if admin_count == 0:
            # Import passlib for password hashing
            try:
                from passlib.context import CryptContext
                pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            except ImportError:
                print("Warning: passlib not available, using plain text password")
                pwd_context = None
            
            admin_id = uuid.uuid4()
            admin_raw_password = os.environ.get("ADMIN_PASSWORD")
            if not admin_raw_password:
                print("Skipping admin user creation: ADMIN_PASSWORD not set")
                return
            
            admin_password = pwd_context.hash(admin_raw_password) if pwd_context else admin_raw_password
            
            now_ts = datetime.utcnow()
            await conn.execute(text("""
                INSERT INTO users (id, email, username, hashed_password, is_active, is_superuser, is_verified, role, full_name, created_at, updated_at)
                VALUES (:id, :email, :username, :password, TRUE, TRUE, TRUE, 'admin', :full_name, :created_at, :updated_at);
            """), {
                "id": admin_id,
                "email": "admin@example.com",
                "username": "admin",
                "password": admin_password,
                "full_name": "Administrator",
                "created_at": now_ts,
                "updated_at": now_ts
            })
            
            print(f"Created default admin user:")
            print(f"  Email: admin@example.com")
            print(f"  Username: admin")
    
    await engine.dispose()
    print("Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_migration())