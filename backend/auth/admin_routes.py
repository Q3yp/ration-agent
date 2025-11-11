import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from fastapi_users.exceptions import UserAlreadyExists
from pydantic import BaseModel
from .database import get_async_session
from .models import User
from .schemas import AdminUserCreate, AdminUserUpdate, UserRead, UserListResponse, UserResponse
from .config import current_superuser, get_user_manager, UserManager

admin_router = APIRouter(prefix="/admin", tags=["admin"])


# Pydantic models for animal type permissions
class AnimalTypePermissionsUpdate(BaseModel):
    allowed_animal_types: Optional[List[str]] = None


class AnimalTypePermissionsResponse(BaseModel):
    user_id: str
    username: str
    allowed_animal_types: Optional[List[str]]
    message: str

@admin_router.get("/users", response_model=UserListResponse)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    admin_user: User = Depends(current_superuser)
):
    """List all users (admin only)"""
    # Get total count
    total_result = await session.execute(select(func.count(User.id)))
    total = total_result.scalar()
    
    # Get users with pagination
    result = await session.execute(
        select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    
    # Convert to UserRead format
    user_reads = []
    for user in users:
        user_reads.append(UserRead(
            id=user.id,
            email=user.email,
            username=user.username,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_verified=user.is_verified,
            full_name=user.full_name,
            role=user.role,
            allowed_animal_types=user.allowed_animal_types,
            preferred_language=user.preferred_language,
            phone_number=user.phone_number,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat()
        ))

    return UserListResponse(users=user_reads, total=total)

@admin_router.post("/users", response_model=UserResponse)
async def create_user(
    user_create: AdminUserCreate,
    session: AsyncSession = Depends(get_async_session),
    user_manager: UserManager = Depends(get_user_manager),
    admin_user: User = Depends(current_superuser)
):
    """Create a new user (admin only)"""
    try:
        # Convert AdminUserCreate to UserCreate format
        from .schemas import UserCreate
        normalized_email = user_create.email.strip() if user_create.email else None
        user_create_data = UserCreate(
            email=normalized_email,
            username=user_create.username,
            password=user_create.password,
            full_name=user_create.full_name,
            role=user_create.role,
            is_active=user_create.is_active,
            is_superuser=user_create.is_superuser,
            is_verified=user_create.is_verified,
            preferred_language=user_create.preferred_language,
            phone_number=user_create.phone_number
        )
        
        user = await user_manager.create(user_create_data)
        
        user_read = UserRead(
            id=user.id,
            email=user.email,
            username=user.username,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_verified=user.is_verified,
            full_name=user.full_name,
            role=user.role,
            preferred_language=user.preferred_language,
            phone_number=user.phone_number,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat()
        )
        
        return UserResponse(
            user=user_read,
            message=f"User {user.username} created successfully"
        )
        
    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@admin_router.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    admin_user: User = Depends(current_superuser)
):
    """Get user by ID (admin only)"""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserRead(
        id=user.id,
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        full_name=user.full_name,
        role=user.role,
        preferred_language=user.preferred_language,
        phone_number=user.phone_number,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat()
    )

@admin_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_update: AdminUserUpdate,
    session: AsyncSession = Depends(get_async_session),
    user_manager: UserManager = Depends(get_user_manager),
    admin_user: User = Depends(current_superuser)
):
    """Update user (admin only)"""
    # Get existing user
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        # Convert AdminUserUpdate to UserUpdate format
        from .schemas import UserUpdate
        update_payload = user_update.dict(exclude_unset=True)
        email_value = update_payload.get("email")
        if email_value is not None:
            update_payload["email"] = email_value.strip() or None

        update_data = UserUpdate(**update_payload)
        
        updated_user = await user_manager.update(update_data, user)
        
        user_read = UserRead(
            id=updated_user.id,
            email=updated_user.email,
            username=updated_user.username,
            is_active=updated_user.is_active,
            is_superuser=updated_user.is_superuser,
            is_verified=updated_user.is_verified,
            full_name=updated_user.full_name,
            role=updated_user.role,
            preferred_language=updated_user.preferred_language,
            phone_number=updated_user.phone_number,
            created_at=updated_user.created_at.isoformat(),
            updated_at=updated_user.updated_at.isoformat()
        )
        
        return UserResponse(
            user=user_read,
            message=f"User {updated_user.username} updated successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@admin_router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user_manager: UserManager = Depends(get_user_manager),
    admin_user: User = Depends(current_superuser)
):
    """Delete user (admin only)"""
    # Get existing user
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deleting themselves
    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    try:
        await user_manager.delete(user)
        return {
            "message": f"User {user.username} deleted successfully",
            "user_id": str(user_id)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@admin_router.put("/users/{user_id}/animal-types", response_model=AnimalTypePermissionsResponse)
async def update_user_animal_types(
    user_id: uuid.UUID,
    permissions: AnimalTypePermissionsUpdate,
    session: AsyncSession = Depends(get_async_session),
    admin_user: User = Depends(current_superuser)
):
    """Update user's allowed animal types (admin only)"""
    # Get existing user
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        # Validate animal types if provided
        if permissions.allowed_animal_types is not None:
            from models import AnimalType
            valid_types = [t.value for t in AnimalType]
            for animal_type in permissions.allowed_animal_types:
                if animal_type not in valid_types:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid animal type: {animal_type}. Valid types: {', '.join(valid_types)}"
                    )

        # Update allowed_animal_types
        user.allowed_animal_types = permissions.allowed_animal_types
        await session.commit()
        await session.refresh(user)

        return AnimalTypePermissionsResponse(
            user_id=str(user.id),
            username=user.username,
            allowed_animal_types=user.allowed_animal_types,
            message=f"Animal type permissions updated for user {user.username}"
        )

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update animal type permissions: {str(e)}"
        )
