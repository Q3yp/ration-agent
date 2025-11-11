import uuid
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, field_validator
from fastapi_users import schemas

class UserRead(schemas.BaseUser[uuid.UUID]):
    """User schema for reading user data"""
    email: Optional[str] = None
    username: str
    full_name: Optional[str] = None
    role: str
    allowed_animal_types: Optional[List[str]] = None
    preferred_language: str
    phone_number: Optional[str] = None
    tier: Literal["free", "paid"] = "free"
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
    email: Optional[str] = None
    password: str
    full_name: Optional[str] = None
    role: str = "user"
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    is_verified: Optional[bool] = False
    preferred_language: str = "zh-CN"
    phone_number: Optional[str] = None
    tier: Literal["free", "paid"] = "free"

class UserUpdate(schemas.BaseUserUpdate):
    """User schema for updating user data"""
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
    preferred_language: Optional[str] = None
    phone_number: Optional[str] = None
    tier: Optional[Literal["free", "paid"]] = None

# Admin-specific schemas
class AdminUserCreate(BaseModel):
    """Admin schema for creating users"""
    username: str
    email: Optional[str] = None
    password: str
    full_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = True
    preferred_language: str = "zh-CN"
    phone_number: Optional[str] = None
    tier: Literal["free", "paid"] = "free"

class AdminUserUpdate(BaseModel):
    """Admin schema for updating users"""
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
    preferred_language: Optional[str] = None
    phone_number: Optional[str] = None
    tier: Optional[Literal["free", "paid"]] = None

class UserListResponse(BaseModel):
    """Response schema for user list"""
    users: list[UserRead]
    total: int
    
class UserResponse(BaseModel):
    """Generic user response"""
    user: UserRead
    message: str


class SMSCodeRequest(BaseModel):
    """Payload for requesting an SMS verification code."""

    mobile: str
    purpose: Literal["register", "login", "bind"] = "register"

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str) -> str:
        sanitized = value.strip().replace(" ", "")
        if not sanitized:
            raise ValueError("仅支持中国大陆手机号")

        if sanitized.startswith("00"):
            sanitized = sanitized[2:]

        if sanitized.startswith("+"):
            sanitized = sanitized[1:]

        if not sanitized.isdigit():
            raise ValueError("仅支持中国大陆手机号")

        if len(sanitized) == 11 and sanitized.startswith("1"):
            sanitized = f"86{sanitized}"

        if not (sanitized.startswith("86") and len(sanitized) == 13):
            raise ValueError("仅支持中国大陆手机号")

        return f"+{sanitized}"


class SMSCodeResponse(BaseModel):
    """Response payload after requesting an SMS verification code."""

    message: str
    expires_in: int


class SMSRegisterRequest(BaseModel):
    """Register a new account using a verified phone number."""

    mobile: str
    code: str
    password: str
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    preferred_language: str = "zh-CN"

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str) -> str:
        return SMSCodeRequest.normalize_mobile(value)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        sanitized = value.strip()
        if not sanitized.isdigit() or len(sanitized) not in (4, 5, 6):
            raise ValueError("Invalid verification code")
        return sanitized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return value


class CredentialsLoginRequest(BaseModel):
    """Login using any identifier plus password."""

    identifier: str
    password: str
