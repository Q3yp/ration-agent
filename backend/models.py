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


# Simplified message format for frontend communication
from typing import Dict, Any, Optional, Literal

MessageType = Literal[
    "user",           # User input message
    "agent",          # Agent response content (streamable)
    "tool_call",      # Tool execution indicator
    "tool_result",    # Tool execution result
    "role_transition", # Agent handoff/routing (single expandable bubble)
    "artifact",       # HTML artifacts for visualization (clickable)
    "file_export"     # File export with download capability
]

class ParsedMessage(BaseModel):
    """
    Simplified unified message format.
    6 types: user, agent, tool_call, tool_result, role_transition, artifact
    """
    id: str
    type: MessageType
    content: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

# Message constructors
def create_user_message(content: str, message_id: str, timestamp: float) -> ParsedMessage:
    """User input message"""
    return ParsedMessage(
        id=message_id,
        type="user", 
        content=content,
        timestamp=timestamp
    )

def create_agent_message(content: str, message_id: str, timestamp: float, is_streaming: bool = False) -> ParsedMessage:
    """Agent response - streamable in real-time, complete in history"""
    return ParsedMessage(
        id=message_id,
        type="agent",
        content=content, 
        timestamp=timestamp,
        metadata={"is_streaming": is_streaming} if is_streaming else None
    )

def create_tool_call_message(tool_name: str, tool_args: Dict[str, Any], tool_id: str, timestamp: float) -> ParsedMessage:
    """Tool execution indicator"""
    return ParsedMessage(
        id=tool_id,
        type="tool_call",
        content=f"Executing {tool_name}",
        timestamp=timestamp,
        metadata={
            "tool_name": tool_name,
            "tool_args": tool_args
        }
    )

def create_tool_result_message(content: str, tool_name: str, tool_id: str, timestamp: float) -> ParsedMessage:
    """Tool execution result"""
    return ParsedMessage(
        id=f"{tool_id}_result",
        type="tool_result", 
        content=content,
        timestamp=timestamp,
        metadata={"tool_name": tool_name}
    )

def create_role_transition_message(to_role: str, message_id: str, timestamp: float) -> ParsedMessage:
    """Simple bubble for agent handoffs"""
    role_messages = {
        "researcher": "🔬 Delegating to researcher",
        "coder": "💻 Delegating to coder", 
        "nutritionist": "🥛 Returning to nutritionist"
    }
    
    transition_message = role_messages.get(to_role, f"Transitioning to {to_role}")
    
    return ParsedMessage(
        id=message_id,
        type="role_transition",
        content=transition_message,
        timestamp=timestamp,
        metadata={
            "to_role": to_role
        }
    )

def create_artifact_message(title: str, description: str, html_content: str, message_id: str, timestamp: float) -> ParsedMessage:
    """Clickable HTML artifact bubble"""
    return ParsedMessage(
        id=message_id,
        type="artifact",
        content=title,
        timestamp=timestamp,
        metadata={
            "title": title,
            "description": description,
            "html_content": html_content
        }
    )

def create_file_export_message(filename: str, file_type: str, filepath: str, message_id: str, timestamp: float) -> ParsedMessage:
    """File export with download capability"""
    return ParsedMessage(
        id=message_id,
        type="file_export",
        content=f"📊 {filename} ready for download",
        timestamp=timestamp,
        metadata={
            "filename": filename,
            "file_type": file_type,
            "filepath": filepath
        }
    )