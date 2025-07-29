"""
Chat History Service for managing conversation history across sessions
Uses LangGraph's AsyncPostgresSaver to retrieve conversation history with tool calls
"""
from typing import List, Dict, Optional, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import asyncio
from message_parser import message_parser


class ChatHistoryService:
    """Service for managing chat history using LangGraph's checkpointer"""
    
    def __init__(self):
        # No direct database connection needed - uses LangGraph's checkpointer
        pass
    
    async def get_session_history_for_frontend_async(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get session history from LangGraph checkpointer with full message data including tool calls"""
        try:
            # Get connection for AsyncPostgresSaver
            from agent import _connection_manager
            pool = await _connection_manager.get_shared_pool()
            
            checkpointer = AsyncPostgresSaver(pool)
            config = {"configurable": {"thread_id": session_id}}
            
            # Get the current state which contains the messages
            try:
                state_snapshot = await checkpointer.aget_tuple(config)
                if state_snapshot and state_snapshot.checkpoint:
                    channel_values = state_snapshot.checkpoint.get("channel_values", {})
                    messages = channel_values.get("messages", [])
                    
                    # Convert message dicts to BaseMessage objects if needed
                    message_objects = []
                    for msg_data in messages:
                        if isinstance(msg_data, dict):
                            msg_type = msg_data.get("type", "").lower()
                            if msg_type == "human":
                                message_objects.append(HumanMessage(content=msg_data.get("content", "")))
                            elif msg_type == "ai":
                                ai_msg = AIMessage(content=msg_data.get("content", ""))
                                # Preserve tool_calls if they exist
                                if "tool_calls" in msg_data and msg_data["tool_calls"]:
                                    ai_msg.tool_calls = msg_data["tool_calls"]
                                message_objects.append(ai_msg)
                            elif msg_type == "system":
                                message_objects.append(SystemMessage(content=msg_data.get("content", "")))
                            elif msg_type == "tool":
                                # Handle tool messages
                                from langchain_core.messages import ToolMessage
                                tool_msg = ToolMessage(
                                    content=msg_data.get("content", ""),
                                    tool_call_id=msg_data.get("tool_call_id", "")
                                )
                                message_objects.append(tool_msg)
                        else:
                            # Already a BaseMessage object
                            message_objects.append(msg_data)
                    
                    # Apply limit if specified
                    if limit and limit > 0:
                        message_objects = message_objects[-limit:]
                    
                    # Parse for frontend
                    return message_parser.parse_messages_for_frontend(message_objects)
                
            except Exception as e:
                print(f"Error getting LangGraph state: {e}")
                
            # Return empty list if no state found
            return []
            
        except Exception as e:
            print(f"Error accessing LangGraph checkpointer: {e}")
            return []
    
    def get_session_history_for_frontend(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Sync wrapper for getting session history"""
        return asyncio.run(self.get_session_history_for_frontend_async(session_id, limit))
    
    async def get_session_summary_async(self, session_id: str) -> Dict:
        """Get summary statistics for a session from LangGraph checkpointer"""
        try:
            # Get connection for AsyncPostgresSaver
            from agent import _connection_manager
            pool = await _connection_manager.get_shared_pool()
            
            checkpointer = AsyncPostgresSaver(pool)
            config = {"configurable": {"thread_id": session_id}}
            
            # Get the current state
            state_snapshot = await checkpointer.aget_tuple(config)
            if state_snapshot and state_snapshot.checkpoint:
                channel_values = state_snapshot.checkpoint.get("channel_values", {})
                messages = channel_values.get("messages", [])
                
                # Count message types
                human_count = sum(1 for msg in messages if isinstance(msg, dict) and msg.get("type") == "human")
                ai_count = sum(1 for msg in messages if isinstance(msg, dict) and msg.get("type") == "ai")
                system_count = sum(1 for msg in messages if isinstance(msg, dict) and msg.get("type") == "system")
                tool_count = sum(1 for msg in messages if isinstance(msg, dict) and msg.get("type") == "tool")
                
                return {
                    "session_id": session_id,
                    "total_messages": len(messages),
                    "human_messages": human_count,
                    "ai_messages": ai_count,
                    "system_messages": system_count,
                    "tool_messages": tool_count,
                    "has_history": len(messages) > 0
                }
            
            return {
                "session_id": session_id,
                "total_messages": 0,
                "human_messages": 0,
                "ai_messages": 0,
                "system_messages": 0,
                "tool_messages": 0,
                "has_history": False
            }
            
        except Exception as e:
            print(f"Error getting session summary: {e}")
            return {
                "session_id": session_id,
                "total_messages": 0,
                "human_messages": 0,
                "ai_messages": 0,
                "system_messages": 0,
                "tool_messages": 0,
                "has_history": False
            }
    
    def get_session_summary(self, session_id: str) -> Dict:
        """Sync wrapper for getting session summary"""
        return asyncio.run(self.get_session_summary_async(session_id))
    
    async def clear_session_history_async(self, session_id: str):
        """Clear all messages for a session by removing checkpoints"""
        try:
            # Note: LangGraph doesn't provide a direct way to clear checkpoints
            # This would require custom implementation or recreating the thread
            print(f"Warning: Cannot clear LangGraph checkpoint history for session {session_id}")
            print("LangGraph checkpoints are immutable - consider using a new session ID")
        except Exception as e:
            print(f"Error clearing session history: {e}")
    
    def clear_session_history(self, session_id: str):
        """Sync wrapper for clearing session history"""
        asyncio.run(self.clear_session_history_async(session_id))


# Global chat history service instance
chat_history_service = ChatHistoryService()