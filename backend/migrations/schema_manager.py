import asyncio
import logging
import os
import uuid
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# Import the base creation logic
from auth.database import create_db_and_tables, DATABASE_URL
from utils.system_feedbases import get_system_feedbases, list_system_feedbase_names

logger = logging.getLogger(__name__)

class SchemaManager:
    """
    Manages database schema updates and migrations in a consolidated, idempotent way.
    Replaces the scattered migration scripts.
    """
    
    def __init__(self):
        self.db_url = DATABASE_URL
        # Ensure async driver
        if not self.db_url.startswith("postgresql+asyncpg://"):
            self.db_url = self.db_url.replace("postgresql://", "postgresql+asyncpg://")
        
        self.engine = create_async_engine(self.db_url, echo=True)

    async def update_schema(self):
        """Run all schema updates"""
        logger.info("Starting schema update...")
        
        # 1. Ensure base tables exist (users, oauth_account via SQLAlchemy models)
        # Note: user_sessions is NOT in auth/models.py, so we handle it manually or rely on add_users_table logic
        try:
            await create_db_and_tables()
            logger.info("Base tables verified.")
        except Exception as e:
            logger.error(f"Error creating base tables: {e}")
            # Continue as we might be fixing things
            
        async with self.engine.begin() as conn:
            # Enable extensions
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
            
            # 2. Ensure user_sessions table exists (if not created by other means)
            await self._ensure_user_sessions_table(conn)
            
            # 3. Ensure sms_verifications table exists
            await self._ensure_sms_verifications_table(conn)
            
            # 4. Apply column updates to 'users' table
            await self._update_users_table(conn)
            
            # 5. Apply column updates to 'user_sessions' table
            await self._update_user_sessions_table(conn)
            
            # 6. Apply updates to 'oauth_account' table
            await self._update_oauth_account_table(conn)
            
            # 7. Create default admin user
            await self._ensure_admin_user(conn)
            
            # 8. Ensure feedbacks table exists
            await self._ensure_feedbacks_table(conn)
            
            # 9. Data migrations (metadata updates)
            await self._migrate_session_metadata(conn)
            
            # 10. Ensure LangGraph tables exist (checkpointer + store)
            # Doing this manually avoids potential hangs in LangGraph's setup() method
            await self._ensure_langgraph_checkpointer_tables(conn)
            await self._ensure_langgraph_store_tables(conn)
            
        await self.engine.dispose()
        logger.info("Schema update completed successfully.")

    async def seed_feedbases(self):
        """Seed system default feedbases into LangGraph store"""
        logger.info("Seeding default feedbases...")
        try:
            feedbases = get_system_feedbases()
            if not feedbases:
                logger.warning("No system feedbases found to seed.")
                return

            # Import here to avoid circular dependencies at module level
            from core.agent import _connection_manager
            store = await _connection_manager.get_shared_store()

            for name, feedbase in feedbases.items():
                namespace = ("system_feedbases", name)
                await store.aput(namespace, "data", feedbase)
                logger.info(f"✓ Stored feedbase: {name}")
                
            logger.info(f"Feedbase seeding completed. Available: {', '.join(list_system_feedbase_names())}")
            
        except Exception as e:
            logger.error(f"Error seeding feedbases: {e}")


    async def _ensure_user_sessions_table(self, conn):
        """Create user_sessions table if it doesn't exist"""
        logger.info("Checking user_sessions table...")
        
        # Check if users table exists first (FK dependency)
        if not await self._table_exists(conn, 'users'):
            logger.warning("users table does not exist yet, cannot create user_sessions (FK dependency)")
            return
        
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
        
        # Indexes
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_active_deleted ON user_sessions(active, deleted);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_last_accessed ON user_sessions(last_accessed);"))

    async def _ensure_sms_verifications_table(self, conn):
        """Create sms_verifications table"""
        logger.info("Checking sms_verifications table...")
        
        # Check if users table exists first (FK dependency)
        if not await self._table_exists(conn, 'users'):
            logger.warning("users table does not exist yet, cannot create sms_verifications (FK dependency)")
            return
        
        await conn.execute(text("""
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
            );
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sms_verifications_expires_at ON sms_verifications(expires_at);"))

    async def _ensure_feedbacks_table(self, conn):
        """Create feedbacks table"""
        logger.info("Checking feedbacks table...")
        
        # Check if users table exists first (FK dependency)
        if not await self._table_exists(conn, 'users'):
            logger.warning("users table does not exist yet, cannot create feedbacks (FK dependency)")
            return
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feedbacks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_id VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                status VARCHAR(50) NOT NULL DEFAULT 'pending'
            );
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feedbacks_user_id ON feedbacks(user_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feedbacks_created_at ON feedbacks(created_at DESC);"))

    async def _update_users_table(self, conn):
        """Apply updates to users table"""
        logger.info("Updating users table schema...")
        
        # Check if users table exists first
        if not await self._table_exists(conn, 'users'):
            logger.warning("users table does not exist yet, skipping column updates")
            return
        
        # allowed_animal_types
        if not await self._column_exists(conn, 'users', 'allowed_animal_types'):
            await conn.execute(text("ALTER TABLE users ADD COLUMN allowed_animal_types JSON NULL"))
            logger.info("Added allowed_animal_types column")
            
        # preferred_language
        if not await self._column_exists(conn, 'users', 'preferred_language'):
            await conn.execute(text("ALTER TABLE users ADD COLUMN preferred_language VARCHAR(10) NOT NULL DEFAULT 'zh-CN'"))
            logger.info("Added preferred_language column")
            
        # phone_number
        if not await self._column_exists(conn, 'users', 'phone_number'):
            await conn.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR(20) UNIQUE"))
            logger.info("Added phone_number column")
            
        # tier
        if not await self._column_exists(conn, 'users', 'tier'):
            await conn.execute(text("ALTER TABLE users ADD COLUMN tier VARCHAR(20) NOT NULL DEFAULT 'free'"))
            logger.info("Added tier column")
            
            # Set default allowed types for free tier if needed
            await conn.execute(text("""
                UPDATE users
                SET allowed_animal_types = '["cat","dog"]'::json
                WHERE (allowed_animal_types IS NULL OR allowed_animal_types::jsonb = '[]'::jsonb)
                AND tier = 'free'
            """))

        # Remove pets_enabled
        if await self._column_exists(conn, 'users', 'pets_enabled'):
            await conn.execute(text("ALTER TABLE users DROP COLUMN pets_enabled"))
            logger.info("Removed pets_enabled column")

        # Make email nullable
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'email' AND is_nullable = 'NO'
                ) THEN
                    ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
                END IF;
            END$$;
        """))

    async def _update_user_sessions_table(self, conn):
        """Apply updates to user_sessions table"""
        logger.info("Updating user_sessions table schema...")
        
        # Check if user_sessions table exists first
        if not await self._table_exists(conn, 'user_sessions'):
            logger.warning("user_sessions table does not exist yet, skipping column updates")
            return
        
        # deleted (already in create, but check to be safe)
        if not await self._column_exists(conn, 'user_sessions', 'deleted'):
            await conn.execute(text("ALTER TABLE user_sessions ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT FALSE"))
            logger.info("Added deleted column")
            
        # stop_requested
        if not await self._column_exists(conn, 'user_sessions', 'stop_requested'):
            await conn.execute(text("ALTER TABLE user_sessions ADD COLUMN stop_requested BOOLEAN DEFAULT FALSE"))
            logger.info("Added stop_requested column")

    async def _update_oauth_account_table(self, conn):
        """Apply updates to oauth_account table"""
        logger.info("Updating oauth_account table schema...")
        
        # Only run ALTER if table exists (might not exist on fresh database)
        if not await self._table_exists(conn, 'oauth_account'):
            logger.info("oauth_account table does not exist yet, skipping column updates")
            return
        
        # Expand tokens to TEXT
        # We can't easily check type in a cross-db way without complex queries, 
        # but ALTER COLUMN TYPE is safe if compatible.
        await conn.execute(text("""
            ALTER TABLE oauth_account
            ALTER COLUMN access_token TYPE TEXT,
            ALTER COLUMN refresh_token TYPE TEXT;
        """))

    async def _ensure_admin_user(self, conn):
        """Create default admin user if none exists"""
        # Check if users table exists first
        if not await self._table_exists(conn, 'users'):
            logger.warning("users table does not exist yet, skipping admin user creation")
            return
            
        result = await conn.execute(text("SELECT COUNT(*) FROM users WHERE is_superuser = TRUE"))
        if result.scalar() == 0:
            logger.info("Creating default admin user...")
            try:
                # Use FastAPI-Users' PasswordHelper (argon2id) for consistency
                from fastapi_users.password import PasswordHelper
                password_helper = PasswordHelper()
                admin_password = password_helper.hash("admin123")
            except ImportError:
                # Fallback to passlib with same argon2id scheme
                from passlib.context import CryptContext
                pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
                admin_password = pwd_context.hash("admin123")
            
            admin_id = uuid.uuid4()
            now = datetime.utcnow()
            
            await conn.execute(text("""
                INSERT INTO users (id, email, username, hashed_password, is_active, is_superuser, is_verified, role, full_name, preferred_language, created_at, updated_at)
                VALUES (:id, :email, :username, :password, TRUE, TRUE, TRUE, 'admin', :full_name, :preferred_language, :created_at, :updated_at)
            """), {
                "id": admin_id,
                "email": "admin@example.com",
                "username": "admin",
                "password": admin_password,
                "full_name": "Administrator",
                "preferred_language": "zh-CN",
                "created_at": now,
                "updated_at": now
            })
            logger.info("Default admin user created.")

    async def _migrate_session_metadata(self, conn):
        """Update session metadata defaults"""
        logger.info("Migrating session metadata...")
        
        # Check if user_sessions table exists first
        if not await self._table_exists(conn, 'user_sessions'):
            logger.warning("user_sessions table does not exist yet, skipping metadata migration")
            return
        
        # animal_type default
        await conn.execute(text("""
            UPDATE user_sessions
            SET metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{animal_type}', '"dairy_cow"')
            WHERE metadata IS NULL OR NOT (metadata ? 'animal_type')
        """))
        
        # token_stats default
        await conn.execute(text("""
            UPDATE user_sessions
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{token_stats}',
                '{"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}'::jsonb
            )
            WHERE metadata IS NULL OR NOT (metadata ? 'token_stats')
        """))

    async def _ensure_langgraph_checkpointer_tables(self, conn):
        """Create LangGraph checkpointer tables to avoid setup() hangs
        
        These tables are normally created by AsyncPostgresSaver.setup() but 
        doing it manually ensures reliable startup without potential freezes.
        Based on langgraph.checkpoint.postgres.base MIGRATIONS.
        """
        logger.info("Ensuring LangGraph checkpointer tables exist...")
        
        # Migration tracking table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS checkpoint_migrations (
                v INTEGER PRIMARY KEY
            );
        """))
        
        # Main checkpoints table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint JSONB NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}',
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
        """))
        
        # Checkpoint blobs for channel data
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS checkpoint_blobs (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                channel TEXT NOT NULL,
                version TEXT NOT NULL,
                type TEXT NOT NULL,
                blob BYTEA,
                PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
            );
        """))
        
        # Checkpoint writes for task execution
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT,
                blob BYTEA NOT NULL,
                task_path TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            );
        """))
        
        # Indexes for performance
        await conn.execute(text("CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);"))
        
        # Record migration versions if not already recorded
        for v in range(10):  # Current migrations count
            await conn.execute(text("""
                INSERT INTO checkpoint_migrations (v) VALUES (:v)
                ON CONFLICT (v) DO NOTHING
            """), {"v": v})
        
        logger.info("✓ LangGraph checkpointer tables ready")

    async def _ensure_langgraph_store_tables(self, conn):
        """Create LangGraph store tables to avoid setup() hangs
        
        These tables are normally created by AsyncPostgresStore.setup() but 
        doing it manually ensures reliable startup without potential freezes.
        Based on langgraph.store.postgres schema.
        """
        logger.info("Ensuring LangGraph store tables exist...")
        
        # Store migrations table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS store_migrations (
                v INTEGER PRIMARY KEY
            );
        """))
        
        # Main store table for key-value storage
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS store (
                prefix TEXT NOT NULL,
                key TEXT NOT NULL,
                value JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMPTZ,
                ttl_minutes INTEGER,
                PRIMARY KEY (prefix, key)
            );
        """))
        
        # Indexes for store
        await conn.execute(text("CREATE INDEX IF NOT EXISTS store_prefix_idx ON store(prefix);"))
        
        # Record migration versions
        for v in range(3):  # Current store migrations count
            await conn.execute(text("""
                INSERT INTO store_migrations (v) VALUES (:v)
                ON CONFLICT (v) DO NOTHING
            """), {"v": v})
        
        logger.info("✓ LangGraph store tables ready")

    async def _table_exists(self, conn, table_name):
        """Check if a table exists"""
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = :table
        """), {"table": table_name})
        return result.scalar() is not None

    async def _column_exists(self, conn, table_name, column_name):
        """Check if a column exists"""
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = :table AND column_name = :col
        """), {"table": table_name, "col": column_name})
        return result.scalar() is not None

async def run_schema_update():
    """Entry point for running updates"""
    load_dotenv()
    manager = SchemaManager()
    await manager.update_schema()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_schema_update())
