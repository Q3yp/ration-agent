from pydantic import BaseModel
from typing import Dict, Any, Optional, Literal, List
from utils.language import normalize_locale, t

MessageType = Literal[
    "user",           # User input message
    "user_input",     # User response to ask_user tool (orange, with questions context)
    "agent",          # Agent response content (streamable)
    "thinking",       # Model reasoning content (streamable, collapsible)
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
    "formulation_complete", # Final feed formulation summary
    "calculation"     # Calculator tool result (formula -> result)
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
def _normalize_tool_content(content: str) -> str:
    """
    Replace common escaped control sequences with their actual characters so the
    frontend renders Markdown/line breaks instead of literal `\n` text.
    """
    if not isinstance(content, str):
        return str(content)

    replacements = {
        r"\n": "\n",
        r"\r": "\r",
        r"\t": "\t",
    }
    for escaped, actual in replacements.items():
        content = content.replace(escaped, actual)
    return content


def create_user_message(content: str, message_id: str, timestamp: float) -> ParsedMessage:
    """User input message"""
    return ParsedMessage(
        id=message_id,
        type="user", 
        content=content,
        timestamp=timestamp
    )

def create_user_input_message(
    content: str, 
    questions: List[str], 
    message_id: str, 
    timestamp: float,
    description: Optional[str] = None
) -> ParsedMessage:
    """User input response to ask_user tool - displayed with questions context"""
    return ParsedMessage(
        id=message_id,
        type="user_input",
        content=content,
        timestamp=timestamp,
        metadata={"description": description, "questions": questions}
    )


def create_agent_message(content: str, message_id: str, timestamp: float, is_streaming: bool = False, metadata: Dict[str, Any] = None) -> ParsedMessage:
    """Agent response - streamable in real-time, complete in history
    
    Args:
        content: The message content
        message_id: Unique message identifier
        timestamp: Unix timestamp
        is_streaming: Whether this is a streaming chunk
        metadata: Optional additional metadata
    """
    # Build metadata dict
    msg_metadata = {}
    if is_streaming:
        msg_metadata["is_streaming"] = True
    if metadata:
        msg_metadata.update(metadata)
    
    return ParsedMessage(
        id=message_id,
        type="agent",
        content=content, 
        timestamp=timestamp,
        metadata=msg_metadata if msg_metadata else None
    )

def create_thinking_message(content: str, message_id: str, timestamp: float, is_streaming: bool = False) -> ParsedMessage:
    """Model reasoning content - streamable, displayed in collapsible indicator
    
    Args:
        content: The reasoning/thinking content
        message_id: Unique message identifier
        timestamp: Unix timestamp
        is_streaming: Whether this is a streaming chunk
    """
    return ParsedMessage(
        id=message_id,
        type="thinking",
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
    content = t("tool.executing", locale, tool_name=tool_name)

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
        content=_normalize_tool_content(content),
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
    role_key = f"role.{to_role}"
    transition_message = t(role_key, locale)
    # If key not found (returns the key itself), use default transition
    if transition_message == role_key:
        transition_message = t("role.transition", locale, role=to_role)
    
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
    description: str = None,
) -> ParsedMessage:
    """File export with download capability"""
    locale = normalize_locale(preferred_language)
    content = f"📊 {t('file.ready_download', locale, filename=filename)}"
    status_label = t("file.status_ready", locale)

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
            "description": description,
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
    # Use simple format with "Initializing..." suffix
    init_text = "Initializing..." if locale == "en-US" else "正在初始化..."
    content = f"{analysis_type}: {init_text}"

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
    init_text = "Initializing..." if locale == "en-US" else "正在初始化..."
    content = f"{formulation_type}: {init_text}"

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

def create_calculation_message(
    expression: str,
    result: str,
    message_id: str,
    timestamp: float,
    preferred_language: str = "zh-CN",
    all_results: Optional[List[str]] = None,
) -> ParsedMessage:
    """Calculator tool result (formula -> result)"""
    locale = normalize_locale(preferred_language)
    content = t("calc.expression", locale, expression=expression)

    metadata = {
        "expression": expression,
        "result": result,  # Keep for backward compatibility
        "preferred_language": locale,
    }

    if all_results:
        metadata["all_results"] = all_results

    return ParsedMessage(
        id=message_id,
        type="calculation",
        content=content,
        timestamp=timestamp,
        metadata=metadata
    )
