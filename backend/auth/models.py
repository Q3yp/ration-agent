import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin, exceptions
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy import (
    GUID,
    SQLAlchemyBaseOAuthAccountTableUUID,
)
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship

Base = declarative_base()

class User(SQLAlchemyBaseUserTable[uuid.UUID], Base):
    """User model with FastAPI-Users integration"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[Optional[str]] = mapped_column(
        String(length=320), unique=True, index=True, nullable=True
    )
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
    allowed_animal_types: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        default=lambda: ["dairy_cow"]  # conference override (was: ["cat", "dog"])
    )  # List of allowed animal types
    preferred_language: Mapped[str] = mapped_column(String(length=10), default="zh-CN")
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(length=20), unique=True, index=True, nullable=True
    )
    tier: Mapped[str] = mapped_column(String(length=20), default="paid")  # conference override (was: "free")
    oauth_accounts: Mapped[List["OAuthAccount"]] = relationship(
        "OAuthAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """OAuth account linkage for social authentication providers."""

    __tablename__ = "oauth_account"

    # Override FK to match custom users table name
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
    user: Mapped[User] = relationship("User", back_populates="oauth_accounts")


class SMSVerification(Base):
    """Persisted SMS verification codes for phone-based registration/login flows."""

    __tablename__ = "sms_verifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    mobile: Mapped[str] = mapped_column(String(length=20), index=True)
    code_hash: Mapped[str] = mapped_column(String(length=255))
    purpose: Mapped[str] = mapped_column(String(length=32), default="register")
    template_id: Mapped[Optional[str]] = mapped_column(String(length=32), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user: Mapped[Optional[User]] = relationship("User", backref="sms_verifications")

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

    async def _username_exists(self, username: str) -> bool:
        result = await self.user_db.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalars().first() is not None

    async def _generate_username(self, email: Optional[str], account_id: str) -> str:
        base = (email.split("@")[0] if email and "@" in email else f"google_{account_id[:8] or account_id}")
        candidate = base or f"user_{account_id[:8] or account_id}"
        suffix = 1
        while await self._username_exists(candidate):
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _truncate_token(self, token: Optional[str]) -> Optional[str]:
        if token and len(token) > 1024:
            return token[:1024]
        return token

    async def oauth_callback(
        self,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: Optional[int] = None,
        refresh_token: Optional[str] = None,
        request: Optional[Request] = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> User:
        oauth_account_dict = {
            "oauth_name": oauth_name,
            "access_token": access_token,
            "account_id": account_id,
            "account_email": account_email,
            "expires_at": expires_at,
            "refresh_token": refresh_token,
        }

        try:
            user = await self.get_by_oauth_account(oauth_name, account_id)
        except exceptions.UserNotExists:
            try:
                user = await self.get_by_email(account_email)
                if not associate_by_email:
                    raise exceptions.UserAlreadyExists()
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
            except exceptions.UserNotExists:
                password = self.password_helper.generate()
                username = await self._generate_username(account_email, account_id)
                user_dict = {
                    "email": account_email,
                    "username": username,
                    "hashed_password": self.password_helper.hash(password),
                    "is_verified": is_verified_by_default,
                }
                user = await self.user_db.create(user_dict)
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
                await self.on_after_register(user, request)
        else:
            for existing_oauth_account in user.oauth_accounts:
                if (
                    existing_oauth_account.account_id == account_id
                    and existing_oauth_account.oauth_name == oauth_name
                ):
                    user = await self.user_db.update_oauth_account(
                        user, existing_oauth_account, oauth_account_dict
                    )

        return user

# Database dependency (will be initialized in config.py)
async def get_user_db(session = None):
    """Get user database instance"""
    from .database import get_async_session
    if session is None:
        async for session in get_async_session():
            yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
    else:
        yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
