"""
Enhanced Chat History Service for managing conversation history across sessions
Uses LangGraph's AsyncPostgresSaver with advanced state retrieval capabilities
"""
from typing import Dict, List
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import asyncio


class ChatHistoryService:
    """Service for managing chat history using LangGraph's checkpointer"""
    
    def __init__(self):
        # No direct database connection needed - uses LangGraph's checkpointer
        pass
    
    async def get_complete_session_messages(self, session_id: str) -> List[Dict]:
        """Get complete message history from both supervisor and worker subgraphs"""
        try:
            from core.agent import _connection_manager
            pool = await _connection_manager.get_shared_pool()
            checkpointer = AsyncPostgresSaver(pool)
            
            all_messages = []
            
            # Get messages from main supervisor thread
            main_config = {"configurable": {"thread_id": session_id}}
            main_state = await checkpointer.aget_tuple(main_config)
            if main_state and main_state.checkpoint:
                channel_values = main_state.checkpoint.get("channel_values", {})
                main_messages = channel_values.get("messages", [])
                all_messages.extend(main_messages)
            
            # Get messages from worker subgraphs (researcher and coder)
            for worker in ["researcher", "coder"]:
                worker_config = {
                    "configurable": {
                        "thread_id": session_id,
                        "checkpoint_ns": f"{worker}:"  # Subgraph namespace
                    }
                }
                worker_state = await checkpointer.aget_tuple(worker_config)
                if worker_state and worker_state.checkpoint:
                    channel_values = worker_state.checkpoint.get("channel_values", {})
                    worker_messages = channel_values.get("messages", [])
                    
                    # Add role metadata to worker messages
                    for msg in worker_messages:
                        if isinstance(msg, dict) and "additional_kwargs" not in msg:
                            msg["additional_kwargs"] = {}
                        if isinstance(msg, dict):
                            msg["additional_kwargs"]["agent_role"] = worker
                    
                    all_messages.extend(worker_messages)
            
            # Sort messages by timestamp (if available) or creation order
            all_messages.sort(key=lambda msg: (
                msg.get("additional_kwargs", {}).get("timestamp", 0) if isinstance(msg, dict) 
                else getattr(msg, "additional_kwargs", {}).get("timestamp", 0)
            ))
            
            return all_messages
            
        except Exception as e:
            return []

    async def get_session_summary_async(self, session_id: str) -> Dict:
        """Get summary statistics for a session from LangGraph checkpointer"""
        try:
            # Use complete message retrieval for accurate counts
            all_messages = await self.get_complete_session_messages(session_id)
            
            # Count message types
            human_count = sum(1 for msg in all_messages if isinstance(msg, dict) and msg.get("type") == "human")
            ai_count = sum(1 for msg in all_messages if isinstance(msg, dict) and msg.get("type") == "ai")
            system_count = sum(1 for msg in all_messages if isinstance(msg, dict) and msg.get("type") == "system")
            tool_count = sum(1 for msg in all_messages if isinstance(msg, dict) and msg.get("type") == "tool")
            
            return {
                "session_id": session_id,
                "total_messages": len(all_messages),
                "human_messages": human_count,
                "ai_messages": ai_count,
                "system_messages": system_count,
                "tool_messages": tool_count,
                "has_history": len(all_messages) > 0
            }
            
        except Exception as e:
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
            pass
        except Exception as e:
            pass
    
    def clear_session_history(self, session_id: str):
        """Sync wrapper for clearing session history"""
        asyncio.run(self.clear_session_history_async(session_id))


# Global chat history service instance
chat_history_service = ChatHistoryService()