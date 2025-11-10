"""
Migration to enlarge oauth_account token columns so we can store full provider tokens.
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
    engine = create_async_engine(DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                ALTER TABLE oauth_account
                ALTER COLUMN access_token TYPE TEXT,
                ALTER COLUMN refresh_token TYPE TEXT;
                """
            )
        )

    await engine.dispose()
    print("Expanded oauth_account access_token/refresh_token columns to TEXT.")


if __name__ == "__main__":
    asyncio.run(run_migration())
