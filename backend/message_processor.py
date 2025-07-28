"""
Message processor for handling LangGraph events and formatting them for frontend consumption.
Handles serialization of tool calls, results, and filtering of non-serializable objects.
"""

import logging
from typing import Dict, Any, Union, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from chat_history_service import chat_history_service

logger = logging.getLogger(__name__)


def clean_tool_args_for_frontend(args: Any) -> Any:
    """
    Remove non-serializable objects like HumanMessage from tool arguments.
    Only return data that should be visible to the frontend.
    """
    if not isinstance(args, dict):
        return args
    
    cleaned = {}
    for key, value in args.items():
        # Skip message objects (HumanMessage, AIMessage, etc.)
        if hasattr(value, '__class__') and 'Message' in value.__class__.__name__:
            logger.debug(f"Filtering out {value.__class__.__name__} from tool args")
            continue
        elif key == 'state' and isinstance(value, dict):
            # Skip state objects that contain messages
            logger.debug("Filtering out 'state' parameter from tool args")
            continue
        elif isinstance(value, dict):
            cleaned[key] = clean_tool_args_for_frontend(value)
        elif isinstance(value, (list, tuple)):
            cleaned[key] = [
                clean_tool_args_for_frontend(item) for item in value 
                if not (hasattr(item, '__class__') and 'Message' in item.__class__.__name__)
            ]
        else:
            cleaned[key] = value
    
    return cleaned


def process_tool_start_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process on_tool_start event for frontend consumption"""
    raw_input = event["data"].get("input", {})
    
    # Clean the tool arguments to remove non-serializable objects
    cleaned_args = clean_tool_args_for_frontend(raw_input)
    
    return {
        "type": "tool_call",
        "tool_id": event["run_id"],
        "tool_name": event["name"],
        "tool_args": cleaned_args,
        "timestamp": event.get("timestamp", 0)
    }


def process_tool_end_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process on_tool_end event for frontend consumption"""
    output = event["data"]["output"]
    
    # Convert output to string, handling various types
    if hasattr(output, 'content'):
        # Handle message objects
        content = str(output.content)
    elif hasattr(output, '__dict__'):
        # Handle complex objects by converting to string representation
        content = str(output)
    else:
        content = str(output)
    
    return {
        "type": "tool_result", 
        "content": content,
        "tool_call_id": event["run_id"],
        "timestamp": event.get("timestamp", 0)
    }


def process_chat_model_stream_event(event: Dict[str, Any], message_id: str, accumulated_content: str) -> Dict[str, Any]:
    """Process on_chat_model_stream event for frontend consumption"""
    chunk_content = event["data"]["chunk"].content
    
    return {
        "type": "agent_chunk",
        "content": chunk_content,
        "message_id": message_id,
        "full_content": accumulated_content + chunk_content,
        "timestamp": event.get("timestamp", 0)
    }


def save_conversation_messages(session_id: str, user_message: str, ai_response: str):
    """Save conversation messages to persistent chat history"""
    try:
        # Save user message
        chat_history_service.add_user_message(session_id, user_message)
        
        # Save AI response
        chat_history_service.add_ai_message(session_id, ai_response)
        
        logger.info(f"Saved conversation messages for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to save conversation messages for session {session_id}: {e}")


def get_conversation_context(session_id: str, max_messages: int = 10) -> str:
    """Get formatted conversation history for context"""
    try:
        return chat_history_service.format_history_for_context(session_id, max_messages)
    except Exception as e:
        logger.error(f"Failed to get conversation context for session {session_id}: {e}")
        return "No previous conversation history available."