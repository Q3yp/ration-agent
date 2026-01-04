from pydantic import BaseModel, Field
from typing import Optional
import uuid

class FeedbackCreate(BaseModel):
    """Request model for submitting feedback"""
    session_id: str = Field(..., description="ID of the session being feedbacked")
    content: str = Field(..., min_length=1, max_length=5000, description="Feedback content")


class FeedbackRead(BaseModel):
    """Response model for reading feedback"""
    id: uuid.UUID
    user_id: uuid.UUID
    session_id: str
    content: str
    created_at: str
    username: Optional[str] = None
