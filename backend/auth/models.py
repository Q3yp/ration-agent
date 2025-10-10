import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Boolean, DateTime, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from fastapi_users import BaseUserManager, UUIDIDMixin
import uuid

Base = declarative_base()

class User(SQLAlchemyBaseUserTable[uuid.UUID], Base):
    """User model with FastAPI-Users integration"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(length=320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(length=100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(length=1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional fields for admin management
    full_name: Mapped[Optional[str]] = mapped_column(String(length=200), nullable=True)
    role: Mapped[str] = mapped_column(String(length=50), default="user")  # user, admin
    allowed_animal_types: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=None)  # List of allowed animal types

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """User manager for FastAPI-Users"""
    
    reset_password_token_secret = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-this-in-production-use-at-least-32-characters")
    verification_token_secret = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-this-in-production-use-at-least-32-characters")

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request=None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request=None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")

# Database dependency (will be initialized in config.py)
async def get_user_db(session = None):
    """Get user database instance"""
    from .database import get_async_session
    if session is None:
        async for session in get_async_session():
            yield SQLAlchemyUserDatabase(session, User)
    else:
        yield SQLAlchemyUserDatabase(session, User)