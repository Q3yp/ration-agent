"""
Unified message parser for handling both streaming and historical message parsing.
Ensures consistent formatting between real-time chat and chat history retrieval.
"""

from typing import Dict, Any, List, Optional
from langchain_core.messages import BaseMessage, AIMessage
from agents.nodes import StreamingResponseParser


class MessageParser:
    """Unified parser for AI messages, tool calls, and frontend formatting"""
    
    def __init__(self):
        self.streaming_parser = StreamingResponseParser()
    
    def parse_ai_message_content(self, content: str) -> Dict[str, Any]:
        """Parse AI message content to extract user-visible portions and action data"""
        if not content:
            return {"display_content": "", "full_content": content, "action_data": None}
        
        # Reset parser for this message
        parser = StreamingResponseParser()
        
        # Process the full stored content to extract user-visible parts and action data
        parsed_result = parser.parse_chunk(content)
        display_content = parsed_result["user_message"]
        
        return {
            "display_content": display_content,
            "full_content": content,
            "action_data": parsed_result.get("action_data")
        }
    
    def extract_tool_calls(self, message: BaseMessage) -> List[Dict[str, Any]]:
        """Extract tool calls information from a message"""
        tool_calls = []
        
        if isinstance(message, AIMessage) and hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append({
                    "id": tool_call.get("id"),
                    "name": tool_call.get("name"), 
                    "args": tool_call.get("args", {})
                })
        
        return tool_calls
    
    def parse_message_for_frontend(self, message: BaseMessage) -> Dict[str, Any]:
        """Parse a single message for frontend consumption"""
        msg_type = message.__class__.__name__.lower().replace("message", "")
        content = message.content
        
        # Parse AI messages to extract user-visible content and action data
        if msg_type == "ai" and content:
            parsed_content = self.parse_ai_message_content(content)
            display_content = parsed_content["display_content"]
            full_content = parsed_content["full_content"]
            action_data = parsed_content["action_data"]
        else:
            display_content = content
            full_content = content
            action_data = None
        
        # Extract tool calls information
        tool_calls = self.extract_tool_calls(message)
        
        result = {
            "type": msg_type,
            "content": display_content,
            "full_content": full_content,
            "tool_calls": tool_calls,
            "action_data": action_data,
            "timestamp": getattr(message, "additional_kwargs", {}).get("timestamp")
        }
        
        # Add tool_call_id for tool messages
        if msg_type == "tool" and hasattr(message, 'tool_call_id'):
            result["tool_call_id"] = message.tool_call_id
        
        return result
    
    def parse_messages_for_frontend(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Parse multiple messages for frontend consumption"""
        return [self.parse_message_for_frontend(msg) for msg in messages]
    
    def parse_streaming_chunk(self, chunk_content: str) -> Dict[str, Any]:
        """Parse streaming chunk content (for real-time chat)"""
        return self.streaming_parser.parse_chunk(chunk_content)


# Global message parser instance
message_parser = MessageParser()