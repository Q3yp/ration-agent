from fastapi import APIRouter
from .config import auth_backend, fastapi_users
from .schemas import UserRead, UserCreate

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