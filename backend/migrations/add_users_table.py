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
        # Create users table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(320) UNIQUE NOT NULL,
                username VARCHAR(100) UNIQUE NOT NULL,
                hashed_password VARCHAR(1024) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                is_superuser BOOLEAN DEFAULT FALSE,
                is_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                full_name VARCHAR(200),
                role VARCHAR(50) DEFAULT 'user'
            );
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
            admin_password = pwd_context.hash("admin123") if pwd_context else "admin123"  # Default admin password
            
            await conn.execute(text("""
                INSERT INTO users (id, email, username, hashed_password, is_active, is_superuser, is_verified, role, full_name)
                VALUES (:id, :email, :username, :password, TRUE, TRUE, TRUE, 'admin', :full_name);
            """), {
                "id": admin_id,
                "email": "admin@example.com",
                "username": "admin",
                "password": admin_password,
                "full_name": "Administrator"
            })
            
            print(f"Created default admin user:")
            print(f"  Email: admin@example.com")
            print(f"  Username: admin")
            print(f"  Password: admin123")
            print(f"  Please change the password after first login!")
    
    await engine.dispose()
    print("Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_migration())