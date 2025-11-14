from pydantic import BaseModel, Field, AliasChoices
from enum import Enum
import uuid
from utils.language import normalize_locale


class AnimalType(str, Enum):
    """Pre-defined animal types - users can only choose from these"""
    DAIRY_COW = "dairy_cow"
    BEEF_COW = "beef_cow"
    CAT = "cat"
    DOG = "dog"

    @classmethod
    def get_display_name(cls, value: str) -> str:
        """Get display name for animal type"""
        names = {
            cls.DAIRY_COW: "奶牛 Dairy Cow",
            cls.BEEF_COW: "肉牛 Beef Cow",
            cls.CAT: "猫 Cat",
            cls.DOG: "狗 Dog",
        }
        return names.get(value, value)


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


# Simplified message format for frontend communication
from typing import Dict, Any, Optional, Literal, List

MessageType = Literal[
    "user",           # User input message
    "agent",          # Agent response content (streamable)
    "tool_call",      # Tool execution indicator
    "tool_result",    # Tool execution result
    "role_transition", # Agent handoff/routing (single expandable bubble)
    "artifact",       # HTML artifacts for visualization (clickable)
    "file_export",    # File export with download capability
    "analysis_start", # Start of Excel analysis block
    "analysis_update", # Live update to Excel analysis
    "analysis_complete", # Final Excel analysis summary
    "formulation_start", # Start of feed formulation block
    "formulation_update", # Live update to feed formulation
    "formulation_complete" # Final feed formulation summary
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

def create_tool_call_message(
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_id: str,
    timestamp: float,
    preferred_language: str = "zh-CN",
) -> ParsedMessage:
    """Tool execution indicator"""
    locale = normalize_locale(preferred_language)
    if locale == "en-US":
        content = f"Executing {tool_name}"
    else:
        content = f"正在执行 {tool_name}"

    return ParsedMessage(
        id=tool_id,
        type="tool_call",
        content=content,
        timestamp=timestamp,
        metadata={
            "tool_name": tool_name,
            "tool_args": tool_args,
            "preferred_language": locale,
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

def create_role_transition_message(
    to_role: str,
    message_id: str,
    timestamp: float,
    preferred_language: str = "zh-CN",
) -> ParsedMessage:
    """Simple bubble for agent handoffs"""
    locale = normalize_locale(preferred_language)
    if locale == "en-US":
        role_messages = {
            "researcher": "🔬 Delegating to researcher",
            "coder": "💻 Delegating to coder",
            "nutritionist": "🥛 Returning to nutritionist"
        }
        default_message = f"Transitioning to {to_role}"
    else:
        role_messages = {
            "researcher": "🔬 正在切换到研究专员",
            "coder": "💻 正在切换到代码专员",
            "nutritionist": "🥛 返回营养师"
        }
        default_message = f"切换到 {to_role}"

    transition_message = role_messages.get(to_role, default_message)
    
    return ParsedMessage(
        id=message_id,
        type="role_transition",
        content=transition_message,
        timestamp=timestamp,
        metadata={
            "to_role": to_role,
            "preferred_language": locale,
        }
    )

def create_file_export_message(
    filename: str,
    file_type: str,
    filepath: str,
    message_id: str,
    timestamp: float,
    preferred_language: str = "zh-CN",
) -> ParsedMessage:
    """File export with download capability"""
    locale = normalize_locale(preferred_language)
    if locale == "en-US":
        content = f"📊 {filename} ready for download"
        status_label = "Ready to download"
    else:
        content = f"📊 {filename} 已准备好下载"
        status_label = "准备下载"

    return ParsedMessage(
        id=message_id,
        type="file_export",
        content=content,
        timestamp=timestamp,
        metadata={
            "filename": filename,
            "file_type": file_type,
            "filepath": filepath,
            "status_label": status_label,
            "preferred_language": locale,
        }
    )

def create_analysis_start_message(
    analysis_type: str,
    message_id: str,
    timestamp: float,
    preferred_language: str = "zh-CN",
) -> ParsedMessage:
    """Start of analysis status block"""
    locale = normalize_locale(preferred_language)
    if locale == "en-US":
        content = f"{analysis_type}: Initializing..."
    else:
        content = f"{analysis_type}: 正在初始化..."

    return ParsedMessage(
        id=message_id,
        type="analysis_start",
        content=content,
        timestamp=timestamp,
        metadata={
            "analysis_type": analysis_type,
            "operations": [],
            "preferred_language": locale,
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

def create_analysis_update_message(operation: str, message_id: str, timestamp: float) -> ParsedMessage:
    """Live update to analysis progress"""
    return ParsedMessage(
        id=message_id,
        type="analysis_update", 
        content=operation,
        timestamp=timestamp,
        metadata={
            "operation": operation
        }
    )

def create_analysis_complete_message(
    summary: str,
    message_id: str,
    timestamp: float,
    operations_count: int = 0,
    operations: list = None,
    preferred_language: str = "zh-CN",
) -> ParsedMessage:
    """Final analysis summary"""
    locale = normalize_locale(preferred_language)
    return ParsedMessage(
        id=message_id,
        type="analysis_complete",
        content=summary,
        timestamp=timestamp,
        metadata={
            "operations_count": operations_count,
            "operations": operations or [],
            "completed": True,
            "preferred_language": locale,
        }
    )

def create_formulation_start_message(
    formulation_type: str,
    message_id: str,
    timestamp: float,
    preferred_language: str = "zh-CN",
) -> ParsedMessage:
    """Start of feed formulation block"""
    locale = normalize_locale(preferred_language)
    if locale == "en-US":
        content = f"{formulation_type}: Initializing..."
    else:
        content = f"{formulation_type}: 正在初始化..."

    return ParsedMessage(
        id=message_id,
        type="formulation_start",
        content=content,
        timestamp=timestamp,
        metadata={
            "formulation_type": formulation_type,
            "operations": [],
            "preferred_language": locale,
        }
    )

def create_formulation_update_message(operation: str, message_id: str, timestamp: float, operation_data: dict = None) -> ParsedMessage:
    """Live update to feed formulation progress"""
    return ParsedMessage(
        id=message_id,
        type="formulation_update", 
        content=operation,
        timestamp=timestamp,
        metadata={
            "operation": operation,
            "operation_data": operation_data or {}
        }
    )

def create_formulation_complete_message(
    summary: str,
    message_id: str,
    timestamp: float,
    operations_count: int = 0,
    operations: list = None,
    formulation_results: dict = None,
    preferred_language: str = "zh-CN",
) -> ParsedMessage:
    """Final feed formulation summary"""
    locale = normalize_locale(preferred_language)
    return ParsedMessage(
        id=message_id,
        type="formulation_complete",
        content=summary,
        timestamp=timestamp,
        metadata={
            "operations_count": operations_count,
            "operations": operations or [],
            "formulation_results": formulation_results or {},
            "completed": True,
            "preferred_language": locale,
        }
    )


# Feedbase management models
class FeedData(BaseModel):
    """Individual feed data structure"""
    dm_percent: float = Field(
        ..., ge=0, le=100, description="Dry matter percentage",
        validation_alias=AliasChoices("dm_percent", "dry_matter_percent")
    )
    nutrients: Dict[str, float] = Field(..., description="Nutrient composition")
    cost_per_kg: float = Field(..., ge=0, description="Cost per kilogram")
    display_name: Optional[str] = Field(
        default=None,
        description="Localized feed name resolved for the current user locale",
    )


class FeedbaseData(BaseModel):
    """Complete feedbase structure"""
    animal_type: AnimalType = AnimalType.DAIRY_COW
    feeds: Dict[str, FeedData] = Field(default_factory=dict, description="Collection of feeds")
    feed_labels: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Optional localized feed names keyed by locale code, e.g. {'en': 'Corn', 'zh': '玉米'}",
    )


class FeedbaseListResponse(BaseModel):
    """Response for listing user's feedbases"""
    feedbases: List[str] = Field(default_factory=list, description="List of feedbase names")


class FeedbaseResponse(BaseModel):
    """Response for getting feedbase details"""
    name: str = Field(..., description="Feedbase name")
    data: FeedbaseData = Field(..., description="Feedbase data")


class FeedbaseUpdateRequest(BaseModel):
    """Request for updating/creating a feedbase"""
    data: FeedbaseData = Field(..., description="Feedbase data to store")


class FeedbaseDeleteResponse(BaseModel):
    """Response for feedbase deletion"""
    message: str = Field(..., description="Success/error message")
    feedbase_name: str = Field(..., description="Name of deleted feedbase")
