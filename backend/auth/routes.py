from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_users.exceptions import UserAlreadyExists
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel, field_validator

from utils.language import SUPPORTED_LANGUAGES, normalize_locale

from .config import (
    auth_backend,
    fastapi_users,
    current_active_user,
    get_user_manager,
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_ENABLED,
)
from .schemas import UserRead, UserCreate, UserUpdate
from .models import User

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


google_request_session = google_requests.Request()


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
