"""
Enhanced Chat History Service for managing conversation history across sessions
Uses LangGraph's AsyncPostgresSaver with advanced state retrieval capabilities
"""
from typing import Dict, List, Tuple
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import asyncio
import logging

logger = logging.getLogger(__name__)


class ChatHistoryService:
    """Service for managing chat history using LangGraph's checkpointer"""

    def __init__(self):
        # No direct database connection needed - uses LangGraph's checkpointer
        pass
    def _message_fingerprint(self, msg) -> str:
        """Create a stable fingerprint for a message to detect duplicates."""
        try:
            if isinstance(msg, dict):
                msg_type = msg.get("type", "unknown")
                content = msg.get("content", "")
                ak = msg.get("additional_kwargs", {}) or {}
                msg_id = msg.get("id") or ak.get("id") or ak.get("message_id")
                tool_call_id = msg.get("tool_call_id") or ak.get("tool_call_id") or ak.get("run_id")
                tool_name = ak.get("tool_name") or msg.get("name", "")
                role = ak.get("agent_role", "")
                timestamp = ak.get("timestamp", ak.get("created_at", 0)) or 0
            else:
                # Object-like message
                msg_type = getattr(msg, "type", getattr(getattr(msg, "__class__", object), "__name__", "unknown").lower())
                content = getattr(msg, "content", "")
                ak = getattr(msg, "additional_kwargs", {}) or {}
                msg_id = getattr(msg, "id", None) or ak.get("id") or ak.get("message_id")
                tool_call_id = getattr(msg, "tool_call_id", None) or ak.get("tool_call_id") or ak.get("run_id")
                tool_name = ak.get("tool_name") or getattr(msg, "name", "")
                role = ak.get("agent_role", "")
                timestamp = getattr(msg, "timestamp", ak.get("timestamp", ak.get("created_at", 0)) or 0)
            if msg_id:
                return f"id:{msg_id}"
            if msg_type == "tool" and tool_call_id:
                return f"tool:{tool_call_id}"
            # Fallback fingerprint from stable content digest
            content_bytes = (content or "").encode("utf-8")
            import hashlib
            digest = hashlib.sha1(content_bytes).hexdigest()
            return f"{msg_type}|{role}|{int(timestamp)}|{digest}|{tool_name}"
        except Exception:
            return f"unknown:{id(msg)}"

    def _deduplicate_messages(self, messages: List[Dict]) -> List[Dict]:
        """Remove duplicate messages while preserving order (first occurrence wins)."""
        seen = set()
        result = []
        for m in messages:
            fp = self._message_fingerprint(m)
            if fp in seen:
                continue
            seen.add(fp)
            result.append(m)
        return result


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


            # Sort messages by timestamp (if available) or creation order
            all_messages.sort(key=lambda msg: (
                msg.get("additional_kwargs", {}).get("timestamp", 0) if isinstance(msg, dict)
                else getattr(msg, "additional_kwargs", {}).get("timestamp", 0)
            ))

            # Sort and deduplicate messages
            all_messages.sort(key=lambda msg: (
                msg.get("additional_kwargs", {}).get("timestamp", 0) if isinstance(msg, dict)
                else getattr(msg, "additional_kwargs", {}).get("timestamp", 0)
            ))
            
            return self._deduplicate_messages(all_messages)

        except Exception as e:
            return []

    def get_session_summary_from_messages(self, session_id: str, messages: List[Dict]) -> Dict:
        """Generate summary statistics from provided messages (optimized - no database access)"""
        try:
            # Count message types from provided messages
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

        except Exception as e:
            logger.error(f"Error generating summary from messages for session {session_id}: {e}")
            return {
                "session_id": session_id,
                "total_messages": 0,
                "human_messages": 0,
                "ai_messages": 0,
                "system_messages": 0,
                "tool_messages": 0,
                "has_history": False
            }

    async def get_session_summary_async(self, session_id: str) -> Dict:
        """Get summary statistics for a session from LangGraph checkpointer (backwards compatibility)"""
        try:
            # Use complete message retrieval for accurate counts
            all_messages = await self.get_complete_session_messages(session_id)
            return self.get_session_summary_from_messages(session_id, all_messages)

        except Exception as e:
            logger.error(f"Error getting session summary for {session_id}: {e}")
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

    async def get_session_data(self, session_id: str) -> tuple[List[Dict], Dict]:
        """Get both complete messages and summary in a single optimized call"""
        try:
            # Single database access for messages
            messages = await self.get_complete_session_messages(session_id)
            
            # Generate summary from retrieved messages (no additional database access)
            summary = self.get_session_summary_from_messages(session_id, messages)
            
            logger.info(f"Retrieved {len(messages)} messages and generated summary for session {session_id}")
            return messages, summary
            
        except Exception as e:
            logger.error(f"Error getting session data for {session_id}: {e}")
            # Return empty data with error summary
            empty_summary = {
                "session_id": session_id,
                "total_messages": 0,
                "human_messages": 0,
                "ai_messages": 0,
                "system_messages": 0,
                "tool_messages": 0,
                "has_history": False
            }
            return [], empty_summary

    def clear_session_history(self, session_id: str):
        """Sync wrapper for clearing session history"""
        asyncio.run(self.clear_session_history_async(session_id))


# Global chat history service instance
chat_history_service = ChatHistoryService()