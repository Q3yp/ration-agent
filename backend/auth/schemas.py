import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from fastapi_users import schemas

class UserRead(schemas.BaseUser[uuid.UUID]):
    """User schema for reading user data"""
    username: str
    full_name: Optional[str] = None
    role: str
    allowed_animal_types: Optional[List[str]] = None
    created_at: str
    updated_at: str

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def serialize_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

class UserCreate(schemas.BaseUserCreate):
    """User schema for creating new users"""
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: str = "user"
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    is_verified: Optional[bool] = False

class UserUpdate(schemas.BaseUserUpdate):
    """User schema for updating user data"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None

# Admin-specific schemas
class AdminUserCreate(BaseModel):
    """Admin schema for creating users"""
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = True

class AdminUserUpdate(BaseModel):
    """Admin schema for updating users"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None

class UserListResponse(BaseModel):
    """Response schema for user list"""
    users: list[UserRead]
    total: int
    
class UserResponse(BaseModel):
    """Generic user response"""
    user: UserRead
    message: str