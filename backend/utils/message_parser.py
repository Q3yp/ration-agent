"""
Simplified unified message parser.
Handles both streaming events and stored messages with identical logic.
Produces 6 message types: user, agent, tool_call, tool_result, role_transition, artifact
"""
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage, SystemMessage
from models import (
    ParsedMessage, 
    create_user_message,
    create_agent_message, 
    create_tool_call_message,
    create_tool_result_message,
    create_role_transition_message,
    create_artifact_message,
    create_file_export_message
)

logger = logging.getLogger(__name__)

class UnifiedMessageParser:
    """
    Single parser for both streaming and history contexts.
    Smart tool handling: combines delegation tools into role transitions,
    detects artifacts, handles normal tool calls/results separately.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.delegation_tools = {
            # LangGraph Swarm tools with custom prefix
            "transfer_to_researcher", "transfer_to_coder", "transfer_to_nutritionist",
            # Legacy supervisor tools
            "transfer_back_to_nutritionist"
        }
        self.pending_delegations = {}  # tool_id -> (tool_name, tool_args, timestamp)
        self.agent_message_counter = 0
        self.current_agent_message_id = None
    
    def _extract_artifact_data(self, content: str) -> Optional[Dict[str, str]]:
        """Extract artifact data from tool result content (legacy fallback)"""
        # This method is now a fallback for any legacy artifact data in tool results
        # New artifacts are created directly from tool calls, not tool results
        
        # Check for legacy artifact data markers (keeping for backwards compatibility)
        start_tag = '[ARTIFACT_DATA]'
        end_tag = '[/ARTIFACT_DATA]'
        
        start_idx = content.find(start_tag)
        if start_idx == -1:
            return None
            
        end_idx = content.find(end_tag)
        if end_idx == -1:
            return None
        
        
        # Simple extraction for legacy support only
        json_start = start_idx + len(start_tag)
        raw_content = content[json_start:end_idx]
        
        first_brace = raw_content.find('{')
        last_brace = raw_content.rfind('}')
        
        if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
            return None
        
        json_str = raw_content[first_brace:last_brace + 1]
        
        try:
            artifact_data = json.loads(json_str)
            if artifact_data.get('title') and artifact_data.get('html_content'):
                return {
                    'title': artifact_data['title'],
                    'description': artifact_data.get('description', ''),
                    'html_content': artifact_data['html_content']
                }
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _extract_file_export_data(self, content: str) -> Optional[Dict[str, str]]:
        """Extract file export data from tool result content"""
        # Simple string extraction instead of regex
        start_tag = '[FILE_EXPORT]'
        end_tag = '[/FILE_EXPORT]'
        
        start_idx = content.find(start_tag)
        if start_idx == -1:
            return None
            
        end_idx = content.find(end_tag)
        if end_idx == -1:
            return None
        
        # Extract JSON content between tags
        json_start = start_idx + len(start_tag)
        file_json = content[json_start:end_idx].strip()
        
        if not file_json:
            return None
        
        try:
            file_data = json.loads(file_json)
            
            if file_data.get('filepath') and file_data.get('filename'):
                return {
                    'filepath': file_data['filepath'],
                    'filename': file_data['filename'],
                    'file_type': file_data.get('type', 'unknown')
                }
                
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return None
    
    
    def _get_delegation_role(self, tool_name: str) -> Optional[str]:
        """Map delegation tool names to roles"""
        mapping = {
            "transfer_to_researcher": "researcher",
            "transfer_to_coder": "coder", 
            "transfer_to_nutritionist": "nutritionist",
            "transfer_back_to_nutritionist": "nutritionist"
        }
        return mapping.get(tool_name)
    
    def parse_message(self, message: BaseMessage, context: str = "history") -> List[ParsedMessage]:
        """
        Parse a single message. Context can be 'streaming' or 'history'.
        Returns list of ParsedMessages.
        """
        timestamp = getattr(message, 'timestamp', message.additional_kwargs.get('timestamp', 0))
        if timestamp == 0:
            timestamp = message.additional_kwargs.get('created_at', 0)
        
        msg_id = getattr(message, 'id', None) or f"msg_{hash(str(message.content))}_{int(timestamp * 1000000)}"
        
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
                is_streaming = context == "streaming"
                result.append(create_agent_message(
                    content=message.content,
                    message_id=msg_id,
                    timestamp=timestamp,
                    is_streaming=is_streaming
                ))
            
            # Process tool calls
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_id = tool_call.get("id", f"tool_{int(timestamp * 1000000)}")
                    tool_args = tool_call.get("args", {})
                    
                    if tool_name in self.delegation_tools:
                        # Store delegation for later combination with result
                        self.pending_delegations[tool_id] = (tool_name, tool_args, timestamp)
                    elif tool_name == "create_artifact":
                        # Create artifact message directly from tool args
                        result.append(create_artifact_message(
                            title=tool_args.get('title', ''),
                            description=tool_args.get('description', ''),
                            html_content=tool_args.get('html_content', ''),
                            message_id=f"{tool_id}_artifact",
                            timestamp=timestamp
                        ))
                    elif tool_name == "export_formulation":
                        # Don't send export_formulation tool calls to frontend
                        pass
                    else:
                        # Regular tool call
                        result.append(create_tool_call_message(
                            tool_name=tool_name,
                            tool_args=tool_args,
                            tool_id=tool_id,
                            timestamp=timestamp
                        ))
            
            return result
        
        elif isinstance(message, ToolMessage):
            tool_id = getattr(message, 'tool_call_id', msg_id)
            
            # Check if this is a delegation tool result
            if tool_id in self.pending_delegations:
                tool_name, tool_args, call_timestamp = self.pending_delegations.pop(tool_id)
                to_role = self._get_delegation_role(tool_name)
                
                # Create single role transition bubble
                return [create_role_transition_message(
                    to_role=to_role,
                    message_id=f"{tool_id}_transition",
                    timestamp=timestamp
                )]
            
            # First, extract any special data and create events
            result = []
            tool_name = getattr(message, 'name', message.additional_kwargs.get('tool_name', 'unknown'))
            
            # Check for file export data and create file export event
            file_export_data = self._extract_file_export_data(message.content)
            if file_export_data:
                result.append(create_file_export_message(
                    filename=file_export_data['filename'],
                    file_type=file_export_data['file_type'],
                    filepath=file_export_data['filepath'],
                    message_id=f"{tool_id}_export",
                    timestamp=timestamp
                ))
            
            # Check for legacy artifact data and create artifact event
            artifact_data = self._extract_artifact_data(message.content)
            if artifact_data:
                result.append(create_artifact_message(
                    title=artifact_data['title'],
                    description=artifact_data['description'],
                    html_content=artifact_data['html_content'],
                    message_id=f"{tool_id}_artifact",
                    timestamp=timestamp
                ))
            
            # Then decide whether to include the raw tool result message
            if tool_name in ["create_artifact", "export_formulation"]:
                # Don't include raw tool result for these tools
                return result
            else:
                # Include the tool result message for other tools
                result.append(create_tool_result_message(
                    content=message.content,
                    tool_name=tool_name,
                    tool_id=tool_id,
                    timestamp=timestamp
                ))
                return result
        
        # Skip system messages and other types
        return []
    
    def parse_messages(self, messages: List[BaseMessage]) -> List[ParsedMessage]:
        """Parse list of messages (for history context)"""
        # Convert dict messages to BaseMessage objects if needed
        converted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                msg_type = msg.get("type", "").lower()
                content = msg.get("content", "")
                additional_kwargs = msg.get("additional_kwargs", {})
                
                if msg_type == "human":
                    converted_messages.append(HumanMessage(content=content, additional_kwargs=additional_kwargs))
                elif msg_type == "ai":
                    ai_msg = AIMessage(content=content, additional_kwargs=additional_kwargs)
                    if "tool_calls" in msg:
                        ai_msg.tool_calls = msg["tool_calls"]
                    converted_messages.append(ai_msg)
                elif msg_type == "tool":
                    converted_messages.append(ToolMessage(
                        content=content, 
                        tool_call_id=msg.get("tool_call_id", ""), 
                        additional_kwargs=additional_kwargs
                    ))
                elif msg_type == "system":
                    converted_messages.append(SystemMessage(content=content, additional_kwargs=additional_kwargs))
            else:
                converted_messages.append(msg)
        
        # Parse all messages
        result = []
        for msg in converted_messages:
            parsed = self.parse_message(msg, context="history")
            result.extend(parsed)
        
        return result
    
    def parse_streaming_event(self, event: Dict[str, Any]) -> List[ParsedMessage]:
        """Parse streaming LangGraph event"""
        event_type = event.get("event", "")
        timestamp = event.get("timestamp", 0)
        
        if event_type == "on_chat_model_start":
            # New AI response starting - increment counter
            self.agent_message_counter += 1
            self.current_agent_message_id = f"{self.session_id}_agent_{self.agent_message_counter}"
            return []  # Don't send anything yet, wait for chunks
        
        elif event_type == "on_chat_model_stream":
            # Agent content chunk - use current message ID
            chunk_content = event["data"]["chunk"].content
            if chunk_content and self.current_agent_message_id:
                return [create_agent_message(
                    content=chunk_content,
                    message_id=self.current_agent_message_id,
                    timestamp=timestamp,
                    is_streaming=True
                )]
        
        elif event_type == "on_chat_model_end":
            # AI response finished - reset current message ID
            self.current_agent_message_id = None
            return []  # Don't send anything
        
        elif event_type == "on_tool_start":
            # Tool call started
            tool_name = event.get("name", "")
            # Get args from LangGraph streaming events
            tool_args = event["data"].get("input", {})
            tool_id = event.get("run_id", f"tool_{int(timestamp * 1000000)}")
            
            
            if tool_name in self.delegation_tools:
                # Store delegation for later combination
                self.pending_delegations[tool_id] = (tool_name, tool_args, timestamp)
                return []  # Don't send anything yet
            elif tool_name == "create_artifact":
                # Create artifact message directly from tool args
                return [create_artifact_message(
                    title=tool_args.get('title', ''),
                    description=tool_args.get('description', ''),
                    html_content=tool_args.get('html_content', ''),
                    message_id=f"{tool_id}_artifact",
                    timestamp=timestamp
                )]
            elif tool_name == "export_formulation":
                # Don't send export_formulation tool calls to frontend
                return []
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
            result_content = str(event["data"].get("output", ""))
            
            
            # Check if this is a delegation tool result
            if tool_id in self.pending_delegations:
                tool_name, tool_args, call_timestamp = self.pending_delegations.pop(tool_id)
                to_role = self._get_delegation_role(tool_name)
                
                # Create single role transition bubble
                return [create_role_transition_message(
                    to_role=to_role,
                    message_id=f"{tool_id}_transition",
                    timestamp=timestamp
                )]
            
            # First, extract any special data and create events
            result = []
            
            # Check for file export data and create file export event
            file_export_data = self._extract_file_export_data(result_content)
            if file_export_data:
                result.append(create_file_export_message(
                    filename=file_export_data['filename'],
                    file_type=file_export_data['file_type'],
                    filepath=file_export_data['filepath'],
                    message_id=f"{tool_id}_export",
                    timestamp=timestamp
                ))
            
            # Check for legacy artifact data and create artifact event
            artifact_data = self._extract_artifact_data(result_content)
            if artifact_data:
                result.append(create_artifact_message(
                    title=artifact_data['title'],
                    description=artifact_data['description'],
                    html_content=artifact_data['html_content'],
                    message_id=f"{tool_id}_artifact",
                    timestamp=timestamp
                ))
            
            # Then decide whether to include the raw tool result message
            if tool_name in ["create_artifact", "export_formulation"]:
                # Don't include raw tool result for these tools
                return result
            else:
                # Include the tool result message for other tools
                result.append(create_tool_result_message(
                    content=result_content,
                    tool_name=tool_name,
                    tool_id=tool_id,
                    timestamp=timestamp
                ))
                return result
        
        # Unknown or unhandled event type
        return []

# No global parser - create per session