from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from utils.language import SUPPORTED_LANGUAGES, normalize_locale
from .config import auth_backend, fastapi_users, current_active_user, get_user_manager
from .schemas import UserRead, UserCreate, UserUpdate
from .models import User

# Create authentication router with FastAPI-Users
auth_router = APIRouter()

# Add FastAPI-Users authentication routes
auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/jwt", tags=["auth"]
)

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
