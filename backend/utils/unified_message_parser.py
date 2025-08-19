"""
Unified message parser that converts raw LangChain messages to ParsedMessage format.
Used by both streaming and history endpoints for consistency.
"""
import logging
from typing import List, Dict, Any, Set
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage, SystemMessage
from models import (
    ParsedMessage, 
    create_user_message,
    create_agent_message, 
    create_tool_call_message,
    create_tool_result_message,
    create_role_transition_message,
    create_error_message,
    create_artifact_message
)

logger = logging.getLogger(__name__)

class UnifiedMessageParser:
    """
    Converts raw LangChain messages to unified ParsedMessage format.
    Handles both real-time streaming events and batch message parsing.
    Uses identical handling rules for consistency.
    """
    
    def __init__(self):
        self.handoff_tools = {"delegate_to_researcher", "delegate_to_coder", "return_to_nutritionist"}
    
    def _parse_artifact_from_content(self, content: str) -> Dict[str, str]:
        """Extract artifact data from tool result content"""
        import re
        import json
        
        # Look for artifact data markers
        artifact_match = re.search(r'\[ARTIFACT_DATA\](.*?)\[/ARTIFACT_DATA\]', content, re.DOTALL)
        if not artifact_match:
            return None
        
        try:
            artifact_json = artifact_match.group(1).strip()
            artifact_data = json.loads(artifact_json)
            
            # Validate required fields
            if artifact_data.get('title') and artifact_data.get('html_content'):
                return {
                    'title': artifact_data['title'],
                    'description': artifact_data.get('description', ''),
                    'html_content': artifact_data['html_content']
                }
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return None
    
    def _clean_content_for_display(self, content: str) -> str:
        """Remove artifact data markers from content"""
        import re
        return re.sub(r'\[ARTIFACT_DATA\].*?\[/ARTIFACT_DATA\]', '', content, flags=re.DOTALL).strip()
    
    def is_handoff_tool(self, tool_name: str) -> bool:
        """Check if a tool is a handoff tool that should be converted to role transition"""
        return tool_name in self.handoff_tools
    
    def should_filter_tool_event(self, tool_name: str) -> bool:
        """Check if a tool event should be filtered out (same logic for streaming and batch)"""
        return self.is_handoff_tool(tool_name)
    
    def create_role_transition_from_tool(self, tool_name: str, tool_args: Dict[str, Any], message_id: str, timestamp: float) -> ParsedMessage:
        """Convert tool call to role transition (same logic for streaming and batch)"""
        tool_to_role = {
            "delegate_to_researcher": "researcher",
            "delegate_to_coder": "coder", 
            "return_to_nutritionist": "nutritionist"
        }
        
        to_role = tool_to_role.get(tool_name)
        if not to_role:
            return None
        
        task_description = tool_args.get("task_description", tool_args.get("findings", ""))
        
        return create_role_transition_message(
            to_role=to_role,
            task_description=task_description,
            message_id=message_id,
            timestamp=timestamp
        )
    
    def parse_messages(self, messages: List[BaseMessage]) -> List[ParsedMessage]:
        """
        Parse a list of raw messages into ParsedMessage format.
        Filters out handoff tool mechanics and generates role transitions.
        """
        # Convert dict messages to BaseMessage objects if needed
        converted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                # Convert dict to appropriate BaseMessage type
                msg_type = msg.get("type", "").lower()
                content = msg.get("content", "")
                if msg_type == "human":
                    converted_messages.append(HumanMessage(content=content, additional_kwargs=msg.get("additional_kwargs", {})))
                elif msg_type == "ai":
                    ai_msg = AIMessage(content=content, additional_kwargs=msg.get("additional_kwargs", {}))
                    if "tool_calls" in msg:
                        ai_msg.tool_calls = msg["tool_calls"]
                    converted_messages.append(ai_msg)
                elif msg_type == "system":
                    converted_messages.append(SystemMessage(content=content, additional_kwargs=msg.get("additional_kwargs", {})))
                elif msg_type == "tool":
                    converted_messages.append(ToolMessage(content=content, tool_call_id=msg.get("tool_call_id", ""), additional_kwargs=msg.get("additional_kwargs", {})))
                else:
                    logger.warning(f"Unknown message type in dict: {msg_type}")
            else:
                # Already a BaseMessage object
                converted_messages.append(msg)
        
        result = []
        handoff_tool_call_ids = set()
        
        # First pass: identify handoff tool call IDs to filter out their results
        for msg in converted_messages:
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.get("name") in self.handoff_tools:
                        handoff_tool_call_ids.add(tool_call.get("id"))
        
        # Second pass: process messages
        for msg in converted_messages:
            parsed_messages = self._parse_single_message(msg, handoff_tool_call_ids)
            result.extend(parsed_messages)
        
        return result
    
    def _parse_single_message(self, message: BaseMessage, handoff_tool_call_ids: Set[str]) -> List[ParsedMessage]:
        """Parse a single message, potentially returning multiple ParsedMessages"""
        msg_id = getattr(message, 'id', f"{hash(message.content)}_{int(message.additional_kwargs.get('timestamp', 0) * 1000000)}")
        timestamp = message.additional_kwargs.get('timestamp', 0)
        
        if isinstance(message, HumanMessage):
            return [create_user_message(
                content=message.content,
                message_id=msg_id,
                timestamp=timestamp
            )]
        
        elif isinstance(message, AIMessage):
            result = []
            
            # Add agent content if present
            if message.content.strip():
                result.append(create_agent_message(
                    content=message.content,
                    message_id=msg_id,
                    timestamp=timestamp
                ))
            
            # Process tool calls
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_id = tool_call.get("id", f"{tool_name}_{timestamp}")
                    
                    if tool_name in self.handoff_tools:
                        # Convert handoff tool to role transition
                        role_transition = self._create_role_transition_from_tool_call(tool_call, msg_id, timestamp)
                        if role_transition:
                            result.append(role_transition)
                    else:
                        # Regular tool call
                        result.append(create_tool_call_message(
                            tool_name=tool_name,
                            tool_args=tool_call.get("args", {}),
                            tool_id=tool_id,
                            timestamp=timestamp
                        ))
            
            return result
        
        elif isinstance(message, ToolMessage):
            # Skip tool results for handoff tools
            if hasattr(message, 'tool_call_id') and message.tool_call_id in handoff_tool_call_ids:
                return []
            
            # Check for artifact data in tool result
            artifact_data = self._parse_artifact_from_content(message.content)
            if artifact_data:
                result = []
                
                # Create artifact message
                result.append(create_artifact_message(
                    title=artifact_data['title'],
                    description=artifact_data['description'],
                    html_content=artifact_data['html_content'],
                    message_id=f"{msg_id}_artifact",
                    timestamp=timestamp
                ))
                
                # Create tool result with cleaned content if there's remaining content
                cleaned_content = self._clean_content_for_display(message.content)
                if cleaned_content:
                    result.append(create_tool_result_message(
                        content=cleaned_content,
                        tool_id=getattr(message, 'tool_call_id', msg_id),
                        timestamp=timestamp
                    ))
                
                return result
            else:
                # Regular tool result without artifact
                return [create_tool_result_message(
                    content=message.content,
                    tool_id=getattr(message, 'tool_call_id', msg_id),
                    timestamp=timestamp
                )]
        
        elif isinstance(message, SystemMessage):
            return [ParsedMessage(
                id=msg_id,
                type="system",
                content=message.content,
                timestamp=timestamp
            )]
        
        else:
            # Unknown message type
            logger.warning(f"Unknown message type: {type(message)}")
            return [ParsedMessage(
                id=msg_id,
                type="system",
                content=str(message.content),
                timestamp=timestamp
            )]
    
    def _create_role_transition_from_tool_call(self, tool_call: Dict[str, Any], message_id: str, timestamp: float) -> ParsedMessage:
        """Convert a handoff tool call to a role transition message"""
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        
        # Map tool names to roles
        tool_to_role = {
            "delegate_to_researcher": "researcher",
            "delegate_to_coder": "coder", 
            "return_to_nutritionist": "nutritionist"
        }
        
        to_role = tool_to_role.get(tool_name)
        if not to_role:
            return None
        
        # Extract task description
        task_description = args.get("task_description", args.get("findings", ""))
        
        return create_role_transition_message(
            to_role=to_role,
            task_description=task_description,
            message_id=f"{message_id}_transition",
            timestamp=timestamp
        )
    
    def parse_streaming_event(self, event: Dict[str, Any]) -> List[ParsedMessage]:
        """
        Parse a real-time LangGraph event into ParsedMessage format.
        Uses same handling rules as batch parsing for consistency.
        """
        event_type = event.get("event", "")
        timestamp = event.get("timestamp", 0)
        
        if event_type == "on_chat_model_stream":
            # Agent content chunk
            chunk_content = event["data"]["chunk"].content
            if chunk_content:
                message_id = f"agent_{int(timestamp * 1000000)}"
                return [create_agent_message(
                    content=chunk_content,
                    message_id=message_id,
                    timestamp=timestamp,
                    is_streaming=True
                )]
        
        elif event_type == "on_tool_start":
            # Tool call started
            tool_name = event.get("name", "")
            tool_args = event["data"].get("input", {}).get("args", {})
            tool_id = event.get("run_id", f"tool_{int(timestamp * 1000000)}")
            
            # Apply same filtering logic as batch parsing
            if self.should_filter_tool_event(tool_name):
                # Convert handoff tool to role transition
                role_transition = self.create_role_transition_from_tool(
                    tool_name, tool_args, tool_id, timestamp
                )
                return [role_transition] if role_transition else []
            else:
                # Regular tool call
                return [create_tool_call_message(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_id=tool_id,
                    timestamp=timestamp
                )]
        
        elif event_type == "on_tool_end":
            # Tool call completed
            tool_name = event.get("name", "")
            tool_id = event.get("run_id", f"tool_{int(timestamp * 1000000)}")
            
            # Apply same filtering logic as batch parsing
            if self.should_filter_tool_event(tool_name):
                # Skip tool results for handoff tools
                return []
            else:
                # Regular tool result - check for artifacts
                result_content = str(event["data"].get("output", ""))
                artifact_data = self._parse_artifact_from_content(result_content)
                
                if artifact_data:
                    result = []
                    
                    # Create artifact message
                    result.append(create_artifact_message(
                        title=artifact_data['title'],
                        description=artifact_data['description'],
                        html_content=artifact_data['html_content'],
                        message_id=f"{tool_id}_artifact",
                        timestamp=timestamp
                    ))
                    
                    # Create tool result with cleaned content if there's remaining content
                    cleaned_content = self._clean_content_for_display(result_content)
                    if cleaned_content:
                        result.append(create_tool_result_message(
                            content=cleaned_content,
                            tool_id=tool_id,
                            timestamp=timestamp
                        ))
                    
                    return result
                else:
                    # Regular tool result without artifact
                    return [create_tool_result_message(
                        content=result_content,
                        tool_id=tool_id,
                        timestamp=timestamp
                    )]
        
        # Unknown or unhandled event type
        return []

# Global parser instance
unified_parser = UnifiedMessageParser()