import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_users.exceptions import UserAlreadyExists
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.hash import bcrypt

from utils.language import SUPPORTED_LANGUAGES, normalize_locale

from .config import (
    auth_backend,
    fastapi_users,
    current_active_user,
    get_user_manager,
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_ENABLED,
)
from .schemas import (
    UserRead,
    UserCreate,
    UserUpdate,
    SMSCodeRequest,
    SMSCodeResponse,
    SMSRegisterRequest,
    CredentialsLoginRequest,
)
from .models import User, SMSVerification
from .database import get_async_session
from .sms_service import sms_client, SMSServiceError

# Create authentication router with FastAPI-Users
auth_router = APIRouter()

# Add FastAPI-Users authentication routes
auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/jwt", tags=["auth"]
)


class GoogleIdTokenRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SMSRegisterResponse(TokenResponse):
    user: UserRead
    message: str = "Registration successful"


SMS_CODE_TTL_SECONDS = int(os.getenv("SMS_CODE_TTL_SECONDS", "600"))
SMS_CODE_RESEND_INTERVAL_SECONDS = int(
    os.getenv("SMS_CODE_RESEND_INTERVAL_SECONDS", "60")
)
SMS_CODE_DAILY_LIMIT = int(os.getenv("SMS_CODE_DAILY_LIMIT", "20"))


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _start_of_day(dt: datetime) -> datetime:
    naive = _to_naive_utc(dt)
    return datetime(naive.year, naive.month, naive.day)


async def _value_exists(session: AsyncSession, column, value: Optional[str]) -> bool:
    if value is None:
        return False
    stmt = select(User.id).where(column == value)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _generate_unique_value(
    session: AsyncSession,
    column,
    base: str,
) -> str:
    candidate = base
    suffix = 1
    while await _value_exists(session, column, candidate):
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _provider_mobile_format(mobile: str) -> str:
    """Convert a normalized +E.164 number into the provider's expected digits."""

    digits = mobile.lstrip("+")
    if digits.startswith("86") and len(digits) >= 13:
        without_cc = digits[2:]
        if len(without_cc) == 11:
            return without_cc
    return digits


def _normalize_identifier_phone(raw: str) -> Optional[str]:
    sanitized = raw.strip().replace(" ", "").replace("-", "")
    if not sanitized:
        return None

    if sanitized.startswith("00"):
        sanitized = sanitized[2:]

    if sanitized.startswith("+"):
        sanitized = sanitized[1:]

    if len(sanitized) == 11 and sanitized.startswith("1"):
        sanitized = f"86{sanitized}"

    if sanitized.startswith("86") and len(sanitized) == 13:
        return f"+{sanitized}"
    return None


async def _find_user_by_identifier(
    session: AsyncSession,
    identifier: str,
) -> Optional[User]:
    trimmed = identifier.strip()
    if not trimmed:
        return None

    stmt = select(User).where(User.username == trimmed)
    result = await session.execute(stmt)
    user = result.scalars().first()
    if user:
        return user

    lowered = trimmed.lower()
    stmt = select(User).where(func.lower(User.email) == lowered)
    result = await session.execute(stmt)
    user = result.scalars().first()
    if user:
        return user

    normalized_phone = _normalize_identifier_phone(trimmed)
    if normalized_phone:
        stmt = select(User).where(User.phone_number == normalized_phone)
        result = await session.execute(stmt)
        user = result.scalars().first()
        if user:
            return user

    return None


google_request_session = google_requests.Request()


@auth_router.post("/sms/code", response_model=SMSCodeResponse, tags=["auth"])
async def request_sms_code(
    payload: SMSCodeRequest,
    session: AsyncSession = Depends(get_async_session),
):
    if not sms_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS provider is not configured on the server.",
        )

    now = _to_naive_utc(datetime.now(timezone.utc))

    latest_stmt = (
        select(SMSVerification)
        .where(
            SMSVerification.mobile == payload.mobile,
            SMSVerification.purpose == payload.purpose,
        )
        .order_by(SMSVerification.created_at.desc())
        .limit(1)
    )
    last_verification = (await session.execute(latest_stmt)).scalars().first()

    if last_verification:
        last_created = _to_naive_utc(last_verification.created_at)
        if (now - last_created).total_seconds() < SMS_CODE_RESEND_INTERVAL_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="验证码发送频率过快，请稍后再试。",
            )

    start_of_day = _start_of_day(now)
    count_stmt = select(func.count(SMSVerification.id)).where(
        SMSVerification.mobile == payload.mobile,
        SMSVerification.created_at >= start_of_day,
    )
    daily_count = (await session.execute(count_stmt)).scalar() or 0

    if daily_count >= SMS_CODE_DAILY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="已达到今日短信发送上限，请明日再试。",
        )

    code = f"{secrets.randbelow(900000) + 100000}"

    try:
        provider_mobile = _provider_mobile_format(payload.mobile)
        response_data = await sms_client.send_verification_code(
            provider_mobile, code, template_id=sms_client.template_id
        )
    except SMSServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    verification = SMSVerification(
        mobile=payload.mobile,
        code_hash=bcrypt.hash(code),
        template_id=response_data.get("templateid"),
        purpose=payload.purpose,
        expires_at=now + timedelta(seconds=SMS_CODE_TTL_SECONDS),
    )

    session.add(verification)
    await session.commit()

    return SMSCodeResponse(message="验证码已发送", expires_in=SMS_CODE_TTL_SECONDS)


@auth_router.post("/sms/register", response_model=SMSRegisterResponse, tags=["auth"])
async def register_with_sms(
    payload: SMSRegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
    strategy=Depends(auth_backend.get_strategy),
):
    if not sms_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS provider is not configured on the server.",
        )

    now = _to_naive_utc(datetime.now(timezone.utc))
    verification_stmt = (
        select(SMSVerification)
        .where(
            SMSVerification.mobile == payload.mobile,
            SMSVerification.purpose == "register",
            SMSVerification.expires_at >= now,
        )
        .order_by(SMSVerification.created_at.desc())
        .limit(1)
    )
    verification = (await session.execute(verification_stmt)).scalars().first()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码不存在或已过期。",
        )

    if verification.verified_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码已被使用。",
        )

    if not bcrypt.verify(payload.code, verification.code_hash):
        verification.attempt_count += 1
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码不正确。",
        )

    existing_phone = (
        await session.execute(
            select(User).where(User.phone_number == payload.mobile)
        )
    ).scalars().first()
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该手机号已注册账号。",
        )

    digits_for_names = payload.mobile.lstrip("+")
    username = payload.username.strip() if payload.username else digits_for_names
    if payload.username:
        if not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名不能为空。",
            )
        if await _value_exists(session, User.username, username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在。",
            )
    else:
        username = await _generate_unique_value(session, User.username, username)

    email = payload.email.strip() if payload.email else None
    if email:
        if await _value_exists(session, User.email, email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已被占用。",
            )

    user_create = UserCreate(
        email=email,
        username=username,
        password=payload.password,
        full_name=payload.full_name,
        preferred_language=payload.preferred_language,
        phone_number=payload.mobile,
        is_verified=True,
    )

    try:
        user = await user_manager.create(user_create)
    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱或用户名已存在。",
        )

    verification.verified_at = now
    verification.user_id = user.id
    await session.commit()

    access_token = await strategy.write_token(user)
    await user_manager.on_after_login(user, request, None)

    user_read = UserRead.model_validate(user, from_attributes=True)
    return SMSRegisterResponse(access_token=access_token, user=user_read)


@auth_router.post("/login", response_model=TokenResponse, tags=["auth"])
async def login_with_identifier(
    payload: CredentialsLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user_manager=Depends(get_user_manager),
    strategy=Depends(auth_backend.get_strategy),
):
    user = await _find_user_by_identifier(session, payload.identifier)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号或密码错误。",
        )

    verified, updated_password_hash = user_manager.password_helper.verify_and_update(
        payload.password, user.hashed_password
    )
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号或密码错误。",
        )

    if updated_password_hash:
        user.hashed_password = updated_password_hash
        session.add(user)
        await session.commit()
        await session.refresh(user)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号已被禁用。",
        )

    access_token = await strategy.write_token(user)
    await user_manager.on_after_login(user, request, None)
    return TokenResponse(access_token=access_token)
@auth_router.post("/google/id-token", response_model=TokenResponse, tags=["auth"])
async def login_with_google_id_token(
    payload: GoogleIdTokenRequest,
    request: Request,
    user_manager=Depends(get_user_manager),
    strategy=Depends(auth_backend.get_strategy),
):
    if not GOOGLE_OAUTH_ENABLED or not GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In is not configured on the server.",
        )

    try:
        id_info = google_id_token.verify_oauth2_token(
            payload.id_token, google_request_session, GOOGLE_OAUTH_CLIENT_ID
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google ID token.",
        ) from exc

    account_id = id_info.get("sub")
    account_email: Optional[str] = id_info.get("email")

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token payload missing subject.",
        )

    if not account_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account did not provide an email address.",
        )

    try:
        user = await user_manager.oauth_callback(
            "google",
            payload.id_token,
            account_id,
            account_email,
            id_info.get("exp"),
            None,
            request,
            associate_by_email=True,
            is_verified_by_default=True,
        )
    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account already linked to another user.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account.",
        )

    access_token = await strategy.write_token(user)
    await user_manager.on_after_login(user, request, None)
    return TokenResponse(access_token=access_token)

# Add user registration route (optional - can be disabled in production)
auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="",
    tags=["auth"],
)

# Add user management routes
auth_router.include_router(
    fastapi_users.get_users_router(UserRead, UserCreate),
    prefix="/users",
    tags=["users"],
)


class UserPreferencesUpdate(BaseModel):
    preferred_language: str

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = normalize_locale(value)
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError("Unsupported language")
        return normalized


@auth_router.patch("/users/me/preferences", response_model=UserRead, tags=["users"])
async def update_user_preferences(
    update: UserPreferencesUpdate,
    current_user: User = Depends(current_active_user),
    user_manager=Depends(get_user_manager),
):
    """Allow authenticated users to update their preferred language."""
    user_update = UserUpdate(preferred_language=update.preferred_language)
    updated_user = await user_manager.update(user_update, current_user)
    return UserRead.model_validate(updated_user, from_attributes=True)
