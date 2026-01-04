"""StopManager: Complete stream lifecycle management with caching and resumability"""
import asyncio
import json
import time
import logging
from enum import Enum
from typing import Dict, List, Any, AsyncIterator, Optional
from services.session_manager import session_manager

logger = logging.getLogger(__name__)


class RequestSource(str, Enum):
    """Source of the streaming request - determines cache replay behavior"""
    STREAM = "stream"    # New message request - skip existing cache
    RESUME = "resume"    # Resume from ask_user - skip existing cache
    HISTORY = "history"  # Reconnect/history tailing - replay full cache


class TokenTrackingState:
    """Maintains token tracking state for a stream"""
    def __init__(self):
        self.latest_conversation_length = 0
        self.run_total_tokens = 0
        self.last_seen_total = 0
        self.last_seen_prompt = 0
        self.run_prompt_delta = 0


def extract_token_event_from_raw(
    raw_event: Dict[str, Any],
    token_state: TokenTrackingState
) -> Optional[Dict[str, Any]]:
    """
    Extract token usage event from raw LangGraph event.
    Updates token_state in-place and returns token_usage_event dict if applicable.

    This function is used by both:
    - Producer: to emit real-time token events during initial stream
    - Resume: to emit token events for new events after reconnection
    """
    try:
        event_type = raw_event.get("event", "unknown")

        # Track streaming events for real-time updates
        if event_type == "on_chat_model_stream":
            data = raw_event.get("data", {})
            chunk = data.get("chunk", {})
            usage_metadata = chunk.usage_metadata if hasattr(chunk, "usage_metadata") else chunk.get("usage_metadata", {}) if isinstance(chunk, dict) else {}

            if usage_metadata:
                abs_prompt = int(usage_metadata.get("input_tokens", 0) or 0)
                abs_completion = int(usage_metadata.get("output_tokens", 0) or 0)
                abs_total = int(usage_metadata.get("total_tokens", 0) or 0)

                if abs_total > 0:
                    delta_prompt = max(0, abs_prompt - token_state.last_seen_prompt)
                    token_state.run_prompt_delta += delta_prompt
                    token_state.last_seen_prompt = abs_prompt

                    token_state.latest_conversation_length = abs_prompt
                    delta_total = max(0, abs_total - token_state.last_seen_total)

                    if delta_total > 0:
                        token_state.run_total_tokens += delta_total
                        token_state.last_seen_total = abs_total

                        return {
                            "_event_type": "token_usage",
                            "token_usage": {
                                "prompt_tokens": token_state.latest_conversation_length,
                                "completion_tokens": abs_completion,
                                "total_tokens": abs_total,
                            },
                            "timestamp": time.time(),
                        }

        # Also track end events as fallback
        elif event_type == "on_chat_model_end":
            data = raw_event.get("data", {})
            output = data.get("output", {})
            response_metadata = output.response_metadata if hasattr(output, "response_metadata") else output.get("response_metadata", {}) if isinstance(output, dict) else {}
            token_usage = response_metadata.get("token_usage", {}) if isinstance(response_metadata, dict) else {}

            if token_usage:
                token_state.latest_conversation_length = int(token_usage.get("prompt_tokens", 0) or 0)
                delta_prompt = max(0, token_state.latest_conversation_length - token_state.last_seen_prompt)
                token_state.run_prompt_delta += delta_prompt
                token_state.last_seen_prompt = token_state.latest_conversation_length

                current_total = int(token_usage.get("total_tokens", 0) or 0)
                delta_total = max(0, current_total - token_state.last_seen_total)

                if delta_total > 0:
                    token_state.run_total_tokens += delta_total
                    token_state.last_seen_total = current_total

                    return {
                        "_event_type": "token_usage",
                        "token_usage": {
                            "prompt_tokens": token_state.latest_conversation_length,
                            "completion_tokens": int(token_usage.get("completion_tokens", 0) or 0),
                            "total_tokens": current_total,
                        },
                        "timestamp": time.time(),
                    }

    except Exception as e:
        logger.warning(f"extract_token_event: Error extracting token event: {e}")

    return None


class StopManager:
    """Singleton stream lifecycle manager with caching and resumability"""

    _instance = None
    _HANDOFF_TOOL_PREFIXES = ("transfer_to_",)
    _HANDOFF_TOOL_NAMES = set()  # Empty set; all handoffs use prefix-based matching

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Session management
        self.active_sessions: Dict[str, List[Dict[str, Any]]] = {}
        self.stream_tasks: Dict[str, asyncio.Task] = {}

        # Track explicit stop requests to distinguish from client disconnects
        self.stop_requests = set()

        # Producer tasks
        self.producer_tasks: Dict[str, asyncio.Task] = {}

        self._initialized = True

    @classmethod
    def get_instance(cls) -> 'StopManager':
        """Get the singleton instance"""
        return cls()

    def _is_handoff_tool(self, tool_name: Any) -> bool:
        if not isinstance(tool_name, str):
            return False
        if any(tool_name.startswith(prefix) for prefix in self._HANDOFF_TOOL_PREFIXES):
            return True
        return tool_name in self._HANDOFF_TOOL_NAMES

    def _is_handoff_event(self, event: Dict[str, Any]) -> bool:
        if not isinstance(event, dict):
            return False
        if event.get("event") != "on_tool_end":
            return False
        return self._is_handoff_tool(event.get("name"))

    def _prune_cache_through_index(self, session_id: str, index: int):
        events = self.active_sessions.get(session_id)
        if not events:
            return
        prune_count = index + 1
        if prune_count >= len(events):
            self.active_sessions[session_id] = []
        else:
            self.active_sessions[session_id] = events[prune_count:]
        logger.debug(f"STOP_MANAGER: Pruned cache through index {index} for session {session_id}")

    async def _producer(
        self,
        session_id: str,
        agent: Any,
        agent_input: Dict[str, Any],
        config: Dict[str, Any]
    ):
        """Producer: Background task that caches LangGraph events (no queue communication)"""
        completed_naturally = False
        is_interrupted = False
        try:
            # Token tracking state for this run
            token_state = TokenTrackingState()

            # Initialize cache if new
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = []

            # Start live LangGraph stream
            agent_events = agent.astream_events(
                agent_input,
                config=config,
                durability="async",
                subgraphs=True
            )

            # Process each live event
            async for raw_event in agent_events:
                try:
                    event_with_timestamp = {**raw_event, "timestamp": time.time()}

                    # 1. Cache raw event
                    self.active_sessions[session_id].append(event_with_timestamp)

                    # 2. Extract and cache token events
                    token_event = extract_token_event_from_raw(raw_event, token_state)
                    if token_event:
                        token_event["session_id"] = session_id
                        self.active_sessions[session_id].append(token_event)

                except Exception as e:
                    logger.error(f"STOP_MANAGER: Error processing live event: {e}")
                    continue

            # Check for interrupt state after stream completes
            # LangGraph interrupt() pauses the graph and stores interrupt info in state
            try:
                current_state = await agent.aget_state(config)
                if hasattr(current_state, 'tasks') and current_state.tasks:
                    for task in current_state.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            for interrupt_info in task.interrupts:
                                interrupt_value = interrupt_info.value if hasattr(interrupt_info, 'value') else interrupt_info
                                if isinstance(interrupt_value, dict) and 'questions' in interrupt_value:
                                    ask_user_event = {
                                        "_event_type": "ask_user",
                                        "description": interrupt_value.get("description"),
                                        "questions": interrupt_value.get("questions", []),
                                        "session_id": session_id,
                                        "timestamp": time.time(),
                                    }
                                    self.active_sessions[session_id].append(ask_user_event)
                                    is_interrupted = True
                                    logger.info(f"STOP_MANAGER: Detected ask_user interrupt for session {session_id}")
            except Exception as e:
                logger.debug(f"STOP_MANAGER: Could not check interrupt state: {e}")

            # Persist accumulated usage to DB (for billing)
            if token_state.run_total_tokens > 0:
                try:
                    run_completion_tokens = max(0, token_state.run_total_tokens - token_state.run_prompt_delta)
                    await session_manager.update_token_usage(
                        session_id,
                        token_state.latest_conversation_length,
                        run_completion_tokens,
                        token_state.run_total_tokens,
                    )
                    logger.info(f"Session {session_id} token usage: prompt={token_state.latest_conversation_length}, completion={run_completion_tokens}, total={token_state.run_total_tokens}")
                except Exception as e:
                    logger.error(f"STOP_MANAGER: Failed to persist token usage for {session_id}: {e}")

            # Mark as naturally completed (not cancelled)
            completed_naturally = True

        except asyncio.CancelledError:
            # Producer was cancelled (manual stop) - preserve cache
            logger.info(f"STOP_MANAGER: Producer cancelled for session {session_id}, preserving cache")
            raise

        except Exception as e:
            logger.error(f"STOP_MANAGER: Producer error for session {session_id}: {e}")

            # Cache error event for frontend
            if session_id in self.active_sessions:
                error_type = type(e).__name__
                error_msg = str(e)
                is_network_error = any(keyword in error_msg.lower() for keyword in [
                    "remote", "connection", "network", "timeout", "disconnect"
                ])

                error_event = {
                    "_event_type": "error",
                    "session_id": session_id,
                    "error": {
                        "type": error_type,
                        "message": error_msg,
                        "is_network_error": is_network_error,
                        "user_message": "Network error occurred. Please try again." if is_network_error else "An error occurred during processing."
                    },
                    "timestamp": time.time(),
                }
                self.active_sessions[session_id].append(error_event)
            raise

        finally:
            # Only cleanup cache if task completed naturally (not cancelled) 
            # AND it's not an interrupt (ask_user) - we want interrupts to survive reloads
            if completed_naturally and not is_interrupted:
                await asyncio.sleep(0.5)
                await self._cleanup_session(session_id)
                logger.info(f"STOP_MANAGER: Natural completion, cache cleared for session {session_id}")
            else:
                # Interrupted or Cancelled -> preserve cache
                if session_id in self.producer_tasks:
                    self.producer_tasks.pop(session_id, None)
                
                reason = "Interrupted (Ask User)" if is_interrupted else "Cancelled/Manual Stop"
                logger.info(f"STOP_MANAGER: Cache preserved for session {session_id} (Reason: {reason})")

    async def stream_to_frontend(
        self,
        session_id: str,
        agent: Any,
        agent_input: Dict[str, Any],
        config: Dict[str, Any],
        title_queue: Optional[Any] = None,
        preferred_language: str = "zh-CN",
        source: RequestSource = RequestSource.STREAM,
    ) -> AsyncIterator[str]:
        """Start producer and stream cached events to frontend (unified with reconnection)"""
        try:
            # If starting a brand new turn (Stream or Resume), we must clear 
            # any previous turn's cached events (like an old ask_user prompt)
            if session_id in self.active_sessions:
                logger.info(f"STOP_MANAGER: Fresh turn start for {session_id}, clearing stale cache")
                self.active_sessions[session_id] = []

            # Start producer in background
            producer_task = asyncio.create_task(self._producer(session_id, agent, agent_input, config))
            self.producer_tasks[session_id] = producer_task

            # Track current stream task for cancellation
            current_task = asyncio.current_task()
            if current_task:
                self.stream_tasks[session_id] = current_task

            # Delegate to unified replay+tail logic
            # Use the provided source (STREAM or RESUME)
            async for sse_event in self.replay_and_tail_cache(
                session_id, 
                title_queue, 
                preferred_language=preferred_language,
                source=source
            ):
                yield sse_event

        except asyncio.CancelledError:
            # Client disconnected - keep producer running for reconnection
            if session_id not in self.stop_requests:
                logger.info(f"STOP_MANAGER: Client disconnected for {session_id}; producer continues")
            raise

        except Exception as e:
            logger.error(f"STOP_MANAGER: Error in stream_to_frontend for {session_id}: {e}")
            raise

        finally:
            # Remove stream task tracking (producer cleanup handled in producer's finally block)
            if session_id in self.stream_tasks:
                self.stream_tasks.pop(session_id, None)

    @classmethod
    async def stop_stream(cls, session_id: str) -> bool:
        """Stop active stream for session using the global singleton instance"""
        try:
            instance = cls.get_instance()
            stopped = False

            # Mark explicit stop for this session (distinguish from client disconnect)
            try:
                instance.stop_requests.add(session_id)
            except Exception:
                pass

            # Cancel main stream task
            if session_id in instance.stream_tasks:
                task = instance.stream_tasks[session_id]
                if not task.cancelled() and not task.done():
                    task.cancel()
                    stopped = True

            # Cancel producer task
            if session_id in instance.producer_tasks:
                producer_task = instance.producer_tasks[session_id]
                if not producer_task.cancelled() and not producer_task.done():
                    producer_task.cancel()
                    stopped = True

            return stopped
        except Exception as e:
            logger.error(f"STOP_MANAGER: Failed to stop stream for session {session_id}: {e}")
            return False

    @classmethod
    async def _cleanup_session(cls, session_id: str):
        """Clean up session from active tracking on the global singleton instance"""
        try:
            instance = cls.get_instance()

            # Clean up active sessions cache
            if session_id in instance.active_sessions:
                instance.active_sessions.pop(session_id)

            # Clean up stream tasks
            if session_id in instance.stream_tasks:
                instance.stream_tasks.pop(session_id)

            # Clean up producer tasks
            if session_id in instance.producer_tasks:
                task = instance.producer_tasks.pop(session_id)
                if not task.done():
                    task.cancel()

            # Clear any stop request flag
            try:
                instance.stop_requests.discard(session_id)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"STOP_MANAGER: Failed to cleanup session {session_id}: {e}")

    @classmethod
    async def is_stream_active(cls, session_id: str) -> bool:
        """Check if stream is currently active on the global singleton instance"""
        instance = cls.get_instance()
        return (session_id in instance.stream_tasks or
                session_id in instance.producer_tasks or
                session_id in instance.active_sessions)

    async def replay_and_tail_cache(
        self,
        session_id: str,
        title_queue: Optional[asyncio.Queue] = None,
        preferred_language: str = "zh-CN",
        source: RequestSource = RequestSource.HISTORY,
    ) -> AsyncIterator[str]:
        """
        Unified cache-based streaming: replay cached events then tail new ones.

        Used by all streaming endpoints (/stream, /history SSE mode, /resume).
        Producer must be started separately before calling this.

        Args:
            source: Request source - STREAM/RESUME skip cache, HISTORY replays full cache

        Yields SSE-formatted events from cache (handles both raw LangGraph events and token events).
        """
        try:
            # Anti-buffering padding
            yield f": {' ' * 2048}\n\n"

            # Connected event
            current_message_id = f"{session_id}_{int(time.time() * 1000000)}"
            yield f"event: connected\ndata: {json.dumps({'message_id': current_message_id, 'session_id': session_id, 'mode': 'stream'})}\n\n"

            # Get parser for this session
            parser = session_manager.get_session_parser(session_id, preferred_language=preferred_language)
            artifact_loading_sent = False

            # Replay all cached events
            # STREAM/RESUME: start at end of current cache (skip existing)
            # HISTORY: replay full cache from start
            skip_cache = source in (RequestSource.STREAM, RequestSource.RESUME)
            cursor = len(self.active_sessions.get(session_id, [])) if skip_cache else 0
            idle_heartbeats = 0

            while True:
                # Check for title updates (non-blocking)
                if title_queue:
                    try:
                        title = title_queue.get_nowait()
                        title_data = {
                            "type": "title_update",
                            "title": title,
                            "session_id": session_id,
                            "timestamp": time.time()
                        }
                        yield f"event: title_update\ndata: {json.dumps(title_data, ensure_ascii=False)}\n\n"
                    except asyncio.QueueEmpty:
                        pass

                # Check if producer is still running (liveness indicator)
                if session_id not in self.producer_tasks:
                    # Producer finished - stream remaining cached events then exit
                    events = self.active_sessions.get(session_id, [])
                    if cursor >= len(events):
                        break  # All events streamed, exit

                # Get current cache (may not exist yet if producer just started)
                events = self.active_sessions.get(session_id, [])

                # Process new events since last cursor
                if cursor > len(events):
                    # Cache was reset/cleared (new turn started) - reset cursor to 0
                    logger.debug(f"STOP_MANAGER: Cache reset detected for {session_id}, cursor={cursor} > len={len(events)}")
                    cursor = 0

                if cursor < len(events):
                    pruned = False
                    for idx, ev in enumerate(events[cursor:], start=cursor):
                        try:
                            # Handle token events (synthesized by producer)
                            if isinstance(ev, dict) and ev.get("_event_type") == "token_usage":
                                token_data = {
                                    "type": "token_usage_update",
                                    "session_id": ev["session_id"],
                                    "token_usage": ev["token_usage"],
                                    "timestamp": ev["timestamp"]
                                }
                                yield f"event: token_usage\ndata: {json.dumps(token_data, ensure_ascii=False)}\n\n"
                                continue

                            # Handle error events
                            if isinstance(ev, dict) and ev.get("_event_type") == "error":
                                error_data = {
                                    "type": "error",
                                    "session_id": ev["session_id"],
                                    "error": ev["error"],
                                    "timestamp": ev["timestamp"]
                                }
                                yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                                continue

                            # Handle ask_user events (agent requesting user input)
                            if isinstance(ev, dict) and ev.get("_event_type") == "ask_user":
                                ask_user_data = {
                                    "type": "ask_user",
                                    "description": ev.get("description"),
                                    "questions": ev.get("questions", []),
                                    "session_id": ev["session_id"],
                                    "timestamp": ev["timestamp"]
                                }
                                yield f"event: ask_user\ndata: {json.dumps(ask_user_data, ensure_ascii=False)}\n\n"
                                continue

                            # Handle regular LangGraph events - parse them
                            parsed_messages = parser.parse_streaming_event(ev)
                            for msg in parsed_messages:
                                # Detect artifact loading (send hint once)
                                if (
                                    msg.type == "agent"
                                    and "create_artifact" in msg.content
                                    and not artifact_loading_sent
                                ):
                                    artifact_loading_sent = True
                                    artifact_loading_data = {
                                        "type": "artifact_loading",
                                        "message_id": current_message_id,
                                        "timestamp": time.time()
                                    }
                                    yield f"event: artifact_loading\ndata: {json.dumps(artifact_loading_data, ensure_ascii=False)}\n\n"

                                # Yield parsed message
                                message_data = msg.dict()
                                yield f"event: message\ndata: {json.dumps(message_data, ensure_ascii=False)}\n\n"

                        except Exception as e:
                            logger.error(f"STOP_MANAGER: Error processing cached event: {e}")
                            continue

                        if self._is_handoff_event(ev):
                            self._prune_cache_through_index(session_id, idx)
                            cursor = 0
                            pruned = True
                            break

                    if pruned:
                        idle_heartbeats = 0
                        continue

                    cursor = len(events)
                    idle_heartbeats = 0
                else:
                    # No new events - send heartbeat periodically
                    idle_heartbeats += 1
                    if idle_heartbeats % 10 == 0:
                        yield ": keep-alive\n\n"
                    await asyncio.sleep(0.2)

            # Final title check
            if title_queue:
                try:
                    title = title_queue.get_nowait()
                    title_data = {
                        "type": "title_update",
                        "title": title,
                        "session_id": session_id,
                        "timestamp": time.time()
                    }
                    yield f"event: title_update\ndata: {json.dumps(title_data, ensure_ascii=False)}\n\n"
                except asyncio.QueueEmpty:
                    pass

            # Stream completed
            completion_data = {
                "type": "agent_complete",
                "message_id": current_message_id,
                "timestamp": time.time()
            }
            yield f"event: complete\ndata: {json.dumps(completion_data, ensure_ascii=False)}\n\n"

        except asyncio.CancelledError:
            # Client disconnected or explicit stop
            if session_id in self.stop_requests:
                stopped_data = {
                    "type": "agent_stopped",
                    "message": "Agent execution stopped by user request",
                    "session_id": session_id,
                    "timestamp": time.time()
                }
                try:
                    yield f"event: stopped\ndata: {json.dumps(stopped_data, ensure_ascii=False)}\n\n"
                except Exception:
                    pass
                self.stop_requests.discard(session_id)
            raise

        except Exception as e:
            logger.error(f"STOP_MANAGER: Error in replay_and_tail_cache for {session_id}: {e}")
            raise
