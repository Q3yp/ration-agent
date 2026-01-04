from pydantic import BaseModel, Field
from typing import List, Optional
from .common import AnimalType

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="The user message")


class ResumeRequest(BaseModel):
    """Request for resuming interrupted agent with user response"""
    response: str = Field(..., min_length=1, max_length=10000, description="User's response to agent question")
    

class ChatResponse(BaseModel):
    message_id: str
    content: str
    type: str
    timestamp: float


class FileUploadResponse(BaseModel):
    message: str
    filename: str
    size: int
    session_id: str
    path: str


class FileListResponse(BaseModel):
    files: list
    session_id: str
    workspace: str


class FileDeleteResponse(BaseModel):
    message: str
    session_id: str


class SessionCreateRequest(BaseModel):
    animal_type: AnimalType = AnimalType.DAIRY_COW


class SessionCreateResponse(BaseModel):
    session_id: str
    animal_type: str
    workspace_path: str
    created_at: str
    message: str
    title: str


class SessionStatsResponse(BaseModel):
    exists: bool
    session_id: str = None
    workspace_path: str = None
    created_at: str = None
    last_accessed: str = None
    active_connections: int = None
    agent_ready: bool = None
    title: str = None


class SessionTitleRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100, description="The session identifier")
    conversation_preview: str = Field(..., min_length=1, max_length=2000, description="Preview of the conversation to generate title from")


class SessionTitleResponse(BaseModel):
    session_id: str
    title: str
    message: str
