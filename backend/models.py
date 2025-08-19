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


# Unified message format for frontend communication
from typing import Dict, Any, Optional, Literal

MessageType = Literal[
    "user",           # User input message
    "agent",          # Agent response content  
    "tool_call",      # Tool being called
    "tool_result",    # Tool execution result
    "role_transition", # Agent handoff/routing
    "artifact",       # HTML artifacts for visualization
    "error",          # Error messages
    "system"          # System messages
]

class ParsedMessage(BaseModel):
    """
    Unified message format for frontend communication.
    Frontend uses 'type' to determine rendering, 'content' for display.
    """
    id: str
    type: MessageType
    content: str
    timestamp: float
    
    # Optional metadata based on message type
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        # Allow extra fields for extensibility
        extra = "allow"

# Convenience constructors for common message types
def create_user_message(content: str, message_id: str, timestamp: float) -> ParsedMessage:
    """Create a user message"""
    return ParsedMessage(
        id=message_id,
        type="user", 
        content=content,
        timestamp=timestamp
    )

def create_agent_message(content: str, message_id: str, timestamp: float, is_streaming: bool = False) -> ParsedMessage:
    """Create an agent response message"""
    return ParsedMessage(
        id=message_id,
        type="agent",
        content=content, 
        timestamp=timestamp,
        metadata={"is_streaming": is_streaming} if is_streaming else None
    )

def create_tool_call_message(tool_name: str, tool_args: Dict[str, Any], tool_id: str, timestamp: float) -> ParsedMessage:
    """Create a tool call message"""
    return ParsedMessage(
        id=tool_id,
        type="tool_call",
        content=f"Calling {tool_name}...",
        timestamp=timestamp,
        metadata={
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_id": tool_id
        }
    )

def create_tool_result_message(content: str, tool_id: str, timestamp: float) -> ParsedMessage:
    """Create a tool result message"""
    return ParsedMessage(
        id=f"{tool_id}_result",
        type="tool_result", 
        content=content,
        timestamp=timestamp,
        metadata={"tool_call_id": tool_id}
    )

def create_role_transition_message(to_role: str, task_description: str, message_id: str, timestamp: float) -> ParsedMessage:
    """Create a role transition message"""
    role_messages = {
        "researcher": "🔬 Delegating to researcher...",
        "coder": "💻 Delegating to coder...", 
        "nutritionist": "🥛 Returning to nutritionist..."
    }
    
    content = role_messages.get(to_role, f"Transitioning to {to_role}...")
    
    return ParsedMessage(
        id=message_id,
        type="role_transition",
        content=content,
        timestamp=timestamp,
        metadata={
            "to_role": to_role,
            "task_description": task_description
        }
    )

def create_error_message(error_text: str, message_id: str, timestamp: float) -> ParsedMessage:
    """Create an error message"""
    return ParsedMessage(
        id=message_id,
        type="error",
        content=error_text,
        timestamp=timestamp
    )

def create_artifact_message(title: str, description: str, html_content: str, message_id: str, timestamp: float) -> ParsedMessage:
    """Create an artifact message for HTML visualizations"""
    return ParsedMessage(
        id=message_id,
        type="artifact",
        content=f"Generated artifact: {title}",
        timestamp=timestamp,
        metadata={
            "title": title,
            "description": description,
            "html_content": html_content
        }
    )