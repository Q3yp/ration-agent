"""
Unified message parser for handling both streaming and historical message parsing.
Ensures consistent formatting between real-time chat and chat history retrieval.
"""

import re
from typing import Dict, Any, List, Optional
from langchain_core.messages import BaseMessage, AIMessage


class StreamingResponseParser:
    """Handles streaming parsing for tool-based responses"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset parser state for new response"""
        self.buffer = ""
        self.full_response = ""
        self.user_content = ""
        self.pending_tool_calls = []
    
    def parse_chunk(self, chunk: str) -> Dict[str, Any]:
        """
        Parse a streaming chunk looking for regular content and tool calls
        """
        # Handle None or non-string chunks
        if chunk is None:
            chunk = ""
        elif not isinstance(chunk, str):
            chunk = str(chunk)
            
        self.buffer += chunk
        self.full_response += chunk
        
        # For tool-based responses, most content is direct user content
        self.user_content += chunk
        
        result = {
            "user_chunk": chunk,
            "action_data": None,
            "is_complete": False,
            "user_message": self.user_content
        }
        
        return result
    
    def parse_tool_call_for_action(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert handoff tool calls to action data for role transitions
        """
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        
        # Map tool names to route names for handoff tools
        handoff_tool_map = {
            "delegate_to_researcher": "researcher",
            "delegate_to_coder": "coder", 
            "return_to_nutritionist": "nutritionist"
        }
        
        if tool_name in handoff_tool_map:
            action_data = {
                "route": handoff_tool_map[tool_name]
            }
            
            # Extract task description or findings
            if "task_description" in args:
                action_data["task"] = args["task_description"]
            elif "findings" in args:
                action_data["finding"] = args["findings"]
            
            return {
                "user_chunk": "",
                "action_data": action_data,
                "is_complete": True,
                "user_message": self.user_content,
                "is_handoff_tool": True
            }
        
        # Not a handoff tool, return normal result
        return {
            "user_chunk": "",
            "action_data": None,
            "is_complete": False,
            "user_message": self.user_content,
            "is_handoff_tool": False
        }


# Removed legacy XML conversion functions - no longer needed with pure tool-based approach


class MessageParser:
    """Unified parser for AI messages, tool calls, and frontend formatting"""
    
    def __init__(self):
        self.streaming_parser = StreamingResponseParser()
    
    def parse_ai_message_content(self, content: str) -> Dict[str, Any]:
        """Parse AI message content - now primarily direct content since we use tools"""
        if not content:
            return {"display_content": "", "full_content": content, "action_data": None}
        
        # With tool-based approach, most content is direct display content
        # Action/routing is handled by tool calls, not embedded content
        return {
            "display_content": content,
            "full_content": content,
            "action_data": None  # Tool calls are handled separately
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
        
        # Check if any tool calls are handoff tools and generate action data
        # Also filter out handoff tools from tool_calls list for frontend
        filtered_tool_calls = []
        if tool_calls and not action_data:
            for tool_call in tool_calls:
                parsed_tool = self.streaming_parser.parse_tool_call_for_action(tool_call)
                if parsed_tool.get("is_handoff_tool") and parsed_tool.get("action_data"):
                    # Use action data from handoff tool but don't include it in tool_calls
                    action_data = parsed_tool["action_data"]
                else:
                    # Keep non-handoff tools in the tool_calls list
                    filtered_tool_calls.append(tool_call)
        else:
            # No handoff tools, keep all tool calls
            filtered_tool_calls = tool_calls
        
        result = {
            "type": msg_type,
            "content": display_content,
            "full_content": full_content,
            "tool_calls": filtered_tool_calls,  # Only non-handoff tool calls
            "action_data": action_data,
            "timestamp": getattr(message, "additional_kwargs", {}).get("timestamp")
        }
        
        # Add tool_call_id for tool messages
        if msg_type == "tool" and hasattr(message, 'tool_call_id'):
            result["tool_call_id"] = message.tool_call_id
        
        return result
    
    def parse_messages_for_frontend(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Parse multiple messages for frontend consumption, filtering out handoff tool messages"""
        result = []
        handoff_tool_call_ids = set()
        
        # First pass: collect handoff tool call IDs
        for msg in messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name", "")
                    if tool_name in ["delegate_to_researcher", "delegate_to_coder", "return_to_nutritionist"]:
                        handoff_tool_call_ids.add(tool_call.get("id"))
        
        # Second pass: parse messages and filter out handoff tool results
        for msg in messages:
            # Skip ToolMessage responses that correspond to handoff tools
            if hasattr(msg, 'tool_call_id') and msg.tool_call_id in handoff_tool_call_ids:
                continue
                
            parsed_msg = self.parse_message_for_frontend(msg)
            result.append(parsed_msg)
        
        return result
    
    def parse_streaming_chunk(self, chunk_content: str) -> Dict[str, Any]:
        """Parse streaming chunk content (for real-time chat)"""
        return self.streaming_parser.parse_chunk(chunk_content)


# Global message parser instance
message_parser = MessageParser()