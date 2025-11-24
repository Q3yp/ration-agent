"""
Database migration to add oauth_account table for social authentication providers.
"""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ration_user:ration_password@localhost:5433/ration_agent",
)

if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


async def run_migration():
    """Create oauth_account table and related indexes."""
    engine = create_async_engine(DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS oauth_account (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    oauth_name VARCHAR(100) NOT NULL,
                    access_token VARCHAR(1024) NOT NULL,
                    expires_at BIGINT,
                    refresh_token VARCHAR(1024),
                    account_id VARCHAR(320) NOT NULL,
                    account_email VARCHAR(320) NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
        )

        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_oauth_account_provider_account
                ON oauth_account(oauth_name, account_id);
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_oauth_account_user_id
                ON oauth_account(user_id);
                """
            )
        )

    await engine.dispose()
    print("OAuth account table migration completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_migration())
