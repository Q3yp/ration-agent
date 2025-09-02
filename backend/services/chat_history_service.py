"""
Enhanced Chat History Service for managing conversation history across sessions
Uses LangGraph's AsyncPostgresSaver with advanced state retrieval capabilities
"""
from typing import Dict, List
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
            logger.info(f"Checking main supervisor thread for session {session_id}")
            main_state = await checkpointer.aget_tuple(main_config)
            if main_state:
                logger.info(f"Main state found: checkpoint={bool(main_state.checkpoint)}, metadata={main_state.metadata}")
                if main_state.checkpoint:
                    channel_values = main_state.checkpoint.get("channel_values", {})
                    logger.info(f"Main checkpoint has channel_values keys: {list(channel_values.keys())}")
                    main_messages = channel_values.get("messages", [])
                    logger.info(f"Retrieved {len(main_messages)} messages from main supervisor thread")
                    all_messages.extend(main_messages)
                else:
                    logger.info("Main state exists but has no checkpoint")
            else:
                logger.info("No main supervisor state found")

            # Get messages from worker subgraphs (researcher and coder)
            for worker in ["researcher", "coder"]:
                logger.info(f"Checking {worker} worker thread for session {session_id}")
                worker_config = {
                    "configurable": {
                        "thread_id": session_id,
                        "checkpoint_ns": f"{worker}:"  # Subgraph namespace
                    }
                }
                worker_state = await checkpointer.aget_tuple(worker_config)
                if worker_state:
                    logger.info(f"{worker} worker state found: checkpoint={bool(worker_state.checkpoint)}, metadata={worker_state.metadata}")
                    if worker_state.checkpoint:
                        channel_values = worker_state.checkpoint.get("channel_values", {})
                        logger.info(f"{worker} checkpoint has channel_values keys: {list(channel_values.keys())}")
                        worker_messages = channel_values.get("messages", [])
                        logger.info(f"Retrieved {len(worker_messages)} messages from {worker} worker")

                        # Add role metadata to worker messages
                        for msg in worker_messages:
                            if isinstance(msg, dict) and "additional_kwargs" not in msg:
                                msg["additional_kwargs"] = {}
                            if isinstance(msg, dict):
                                msg["additional_kwargs"]["agent_role"] = worker

                        all_messages.extend(worker_messages)
                    else:
                        logger.info(f"{worker} worker state exists but has no checkpoint")
                else:
                    logger.info(f"No {worker} worker state found")

            # Sort messages by timestamp (if available) or creation order
            all_messages.sort(key=lambda msg: (
                msg.get("additional_kwargs", {}).get("timestamp", 0) if isinstance(msg, dict)
                else getattr(msg, "additional_kwargs", {}).get("timestamp", 0)
            ))

            # Deduplicate while preserving chronological order
            before = len(all_messages)
            deduped_messages = self._deduplicate_messages(all_messages)
            after = len(deduped_messages)
            if after != before:
                logger.info(f"Deduplicated messages: {before} -> {after}")

            return deduped_messages

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