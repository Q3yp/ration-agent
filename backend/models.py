from pydantic import BaseModel, Field
import uuid


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="The user message")
    

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
    session_id: str = Field(..., min_length=1, max_length=100, description="The session identifier")


class SessionCreateResponse(BaseModel):
    session_id: str
    workspace_path: str
    created_at: str
    message: str


class SessionStatsResponse(BaseModel):
    exists: bool
    session_id: str = None
    workspace_path: str = None
    created_at: str = None
    last_accessed: str = None
    active_connections: int = None
    agent_ready: bool = None