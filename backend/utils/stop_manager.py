"""StopManager: Complete stream lifecycle management with caching and resumability"""
import asyncio
import json
import time
import logging
from typing import Dict, List, Any, AsyncIterator, Optional
from services.session_manager import session_manager

logger = logging.getLogger(__name__)


class StopManager:
    """Singleton stream lifecycle manager with caching and resumability"""

    _instance = None

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

        # Producer/Consumer architecture
        self.message_queues: Dict[str, asyncio.Queue] = {}
        self.producer_tasks: Dict[str, asyncio.Task] = {}

        self._initialized = True

    @classmethod
    def get_instance(cls) -> 'StopManager':
        """Get the singleton instance"""
        return cls()

    async def _producer(
        self,
        session_id: str,
        agent: Any,
        agent_input: Dict[str, Any],
        config: Dict[str, Any]
    ):
        """Producer: Background task that intercepts LangGraph events and puts parsed messages in queue"""
        try:
            queue = self.message_queues[session_id]

            # Initialize per-run token aggregation and fetch current session totals
            base_prompt_tokens = 0
            base_completion_tokens = 0
            base_total_tokens = 0
            try:
                stats = await session_manager.get_session_stats(session_id)
                if stats and stats.get("token_usage"):
                    base_prompt_tokens = int(stats["token_usage"].get("prompt_tokens", 0) or 0)
                    base_completion_tokens = int(stats["token_usage"].get("completion_tokens", 0) or 0)
                    base_total_tokens = int(stats["token_usage"].get("total_tokens", 0) or 0)
            except Exception as e:
                logger.warning(f"STOP_MANAGER: Failed to fetch base token totals for {session_id}: {e}")

            run_prompt_tokens = 0
            run_completion_tokens = 0
            run_total_tokens = 0

            # Track last-sent cumulative session total to avoid duplicate token_usage emissions
            last_sent_total_tokens = base_total_tokens

            # Track the last-seen absolute usage for the current model call to compute deltas safely
            current_call_last_prompt = 0
            current_call_last_completion = 0
            current_call_last_total = 0

            # Handle cached events first if any
            if session_id in self.active_sessions:
                cached_events = self.active_sessions[session_id]
                for cached_event in cached_events:
                    try:
                        parser = session_manager.get_session_parser(session_id)
                        parsed_messages = parser.parse_streaming_event(cached_event)
                        for parsed_msg in parsed_messages:
                            await queue.put(parsed_msg)
                    except Exception as e:
                        logger.error(f"STOP_MANAGER: Error processing cached event: {e}")

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

                    # Cache the event
                    self.active_sessions[session_id].append(event_with_timestamp)

                    # Unified token usage handling (chunk-level and end-of-call)
                    event_type = raw_event.get("event", "unknown")

                    if event_type == "on_chat_model_start":
                        # Reset per-call baseline
                        current_call_last_prompt = 0
                        current_call_last_completion = 0
                        current_call_last_total = 0

                    elif event_type == "on_chat_model_stream":
                        data = raw_event.get("data", {})
                        chunk = data.get("chunk", {})
                        usage = None
                        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                            usage = chunk.usage_metadata
                        elif isinstance(chunk, dict) and chunk.get("usage_metadata"):
                            usage = chunk.get("usage_metadata")

                        if usage is not None:
                            # Some providers expose input/output/total on usage_metadata
                            abs_prompt = getattr(usage, "input_tokens", None)
                            abs_completion = getattr(usage, "output_tokens", None)
                            abs_total = getattr(usage, "total_tokens", None)
                            # Fallbacks if usage is a dict-like object
                            if abs_prompt is None and isinstance(usage, dict):
                                abs_prompt = usage.get("input_tokens")
                            if abs_completion is None and isinstance(usage, dict):
                                abs_completion = usage.get("output_tokens")
                            if abs_total is None and isinstance(usage, dict):
                                abs_total = usage.get("total_tokens")

                            abs_prompt = int(abs_prompt or 0)
                            abs_completion = int(abs_completion or 0)
                            abs_total = int(abs_total or (abs_prompt + abs_completion))

                            # Compute deltas safely (never negative)
                            d_prompt = max(0, abs_prompt - current_call_last_prompt)
                            d_completion = max(0, abs_completion - current_call_last_completion)
                            d_total = max(0, abs_total - current_call_last_total)

                            if d_prompt or d_completion or d_total:
                                run_prompt_tokens += d_prompt
                                run_completion_tokens += d_completion
                                run_total_tokens += d_total

                                current_call_last_prompt = abs_prompt
                                current_call_last_completion = abs_completion
                                current_call_last_total = abs_total

                                # Emit live cumulative session totals to frontend only if changed
                                new_total = base_total_tokens + run_total_tokens
                                if new_total > last_sent_total_tokens:
                                    token_usage_event = {
                                        "_event_type": "token_usage",
                                        "session_id": session_id,
                                        "token_usage": {
                                            "prompt_tokens": base_prompt_tokens + run_prompt_tokens,
                                            "completion_tokens": base_completion_tokens + run_completion_tokens,
                                            "total_tokens": new_total,
                                        },
                                        "timestamp": time.time(),
                                    }
                                    await queue.put(token_usage_event)
                                    last_sent_total_tokens = new_total

                    elif event_type == "on_chat_model_end":
                        data = raw_event.get("data", {})
                        output = data.get("output", {})
                        if hasattr(output, "response_metadata"):
                            response_metadata = output.response_metadata
                        elif isinstance(output, dict):
                            response_metadata = output.get("response_metadata", {})
                        else:
                            response_metadata = {}

                        token_usage = {}
                        if isinstance(response_metadata, dict):
                            token_usage = response_metadata.get("token_usage", {}) or {}

                        if token_usage:
                            abs_prompt = int(token_usage.get("prompt_tokens", 0) or 0)
                            abs_completion = int(token_usage.get("completion_tokens", 0) or 0)
                            abs_total = int(token_usage.get("total_tokens", abs_prompt + abs_completion) or 0)

                            # Compute deltas vs last seen for this call
                            d_prompt = max(0, abs_prompt - current_call_last_prompt)
                            d_completion = max(0, abs_completion - current_call_last_completion)
                            d_total = max(0, abs_total - current_call_last_total)

                            if d_prompt or d_completion or d_total:
                                run_prompt_tokens += d_prompt
                                run_completion_tokens += d_completion
                                run_total_tokens += d_total

                                current_call_last_prompt = abs_prompt
                                current_call_last_completion = abs_completion
                                current_call_last_total = abs_total

                                # Emit live cumulative session totals to frontend only if changed
                                new_total = base_total_tokens + run_total_tokens
                                if new_total > last_sent_total_tokens:
                                    token_usage_event = {
                                        "_event_type": "token_usage",
                                        "session_id": session_id,
                                        "token_usage": {
                                            "prompt_tokens": base_prompt_tokens + run_prompt_tokens,
                                            "completion_tokens": base_completion_tokens + run_completion_tokens,
                                            "total_tokens": new_total,
                                        },
                                        "timestamp": time.time(),
                                    }
                                    await queue.put(token_usage_event)
                                    last_sent_total_tokens = new_total

                    # Parse and put in queue immediately
                    parser = session_manager.get_session_parser(session_id)
                    parsed_messages = parser.parse_streaming_event(event_with_timestamp)
                    for parsed_msg in parsed_messages:
                        await queue.put(parsed_msg)

                except Exception as e:
                    logger.error(f"STOP_MANAGER: Error processing live event: {e}")
                    continue

            # Persist final per-run totals (single atomic DB update) and emit final event only if changed
            if run_total_tokens > 0:
                try:
                    await session_manager.update_token_usage(
                        session_id,
                        run_prompt_tokens,
                        run_completion_tokens,
                        run_total_tokens,
                    )
                    logger.info(
                        f"Session {session_id} token usage (run): prompt={run_prompt_tokens}, completion={run_completion_tokens}, total={run_total_tokens}"
                    )
                except Exception as e:
                    logger.error(f"STOP_MANAGER: Failed to persist token usage for {session_id}: {e}")

                # Only emit a final cumulative event if not already sent
                final_total = base_total_tokens + run_total_tokens
                if final_total > last_sent_total_tokens:
                    final_token_usage_event = {
                        "_event_type": "token_usage",
                        "session_id": session_id,
                        "token_usage": {
                            "prompt_tokens": base_prompt_tokens + run_prompt_tokens,
                            "completion_tokens": base_completion_tokens + run_completion_tokens,
                            "total_tokens": final_total,
                        },
                        "timestamp": time.time(),
                    }
                    await queue.put(final_token_usage_event)
                    last_sent_total_tokens = final_total

            # Signal completion
            await queue.put(None)

        except Exception as e:
            logger.error(f"STOP_MANAGER: Producer error for session {session_id}: {e}")
            # Signal error to consumer
            if session_id in self.message_queues:
                await self.message_queues[session_id].put(None)
            raise

    async def stream_to_frontend(
        self,
        session_id: str,
        agent: Any,
        agent_input: Dict[str, Any],
        config: Dict[str, Any],
        title_queue: Optional[Any] = None
    ) -> AsyncIterator[str]:
        """Consumer: Read from queue and stream SSE events to frontend"""
        logger.error(f"STOPMANAGER_DEBUG: stream_to_frontend called for {session_id}")

        try:
            # Setup producer/consumer
            self.message_queues[session_id] = asyncio.Queue()
            producer_task = asyncio.create_task(self._producer(session_id, agent, agent_input, config))
            self.producer_tasks[session_id] = producer_task

            # Ensure cleanup even if client disconnects (producer completion triggers cleanup)
            def _on_done(t: asyncio.Task):
                try:
                    asyncio.create_task(self._cleanup_session(session_id))
                except Exception as e:
                    logger.error(f"STOP_MANAGER: Failed to schedule cleanup for {session_id}: {e}")
            producer_task.add_done_callback(_on_done)

            # Track for cancellation
            current_task = asyncio.current_task()
            if current_task:
                self.stream_tasks[session_id] = current_task

            # Anti-buffering padding to force flush through proxies (Nginx/Cloudflare/etc.)
            # Sends a 2KB comment which many proxies will forward immediately
            yield f": {' ' * 2048}\n\n"

            # Initial connection event
            current_message_id = f"{session_id}_{int(time.time() * 1000000)}"
            yield f"event: connected\ndata: {json.dumps({'message_id': current_message_id, 'session_id': session_id, 'mode': 'stream'})}\n\n"

            artifact_loading_sent = False
            queue = self.message_queues[session_id]

            # Consumer loop - read from queue and yield immediately
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

                # Get next parsed message from producer (with heartbeat to defeat buffering)
                try:
                    parsed_msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Send periodic keep-alive comment to keep connection open and force flush
                    yield ": keep-alive\n\n"
                    continue

                # Check for completion signal
                if parsed_msg is None:
                    break

                # Handle special token usage event
                if isinstance(parsed_msg, dict) and parsed_msg.get("_event_type") == "token_usage":
                    token_data = {
                        "type": "token_usage_update",
                        "session_id": parsed_msg["session_id"],
                        "token_usage": parsed_msg["token_usage"],
                        "timestamp": parsed_msg["timestamp"]
                    }
                    yield f"event: token_usage\ndata: {json.dumps(token_data, ensure_ascii=False)}\n\n"
                    continue

                # Handle artifact loading detection
                if parsed_msg.type == "agent" and "create_artifact" in parsed_msg.content and not artifact_loading_sent:
                    artifact_loading_sent = True
                    artifact_loading_data = {
                        "type": "artifact_loading",
                        "message_id": current_message_id,
                        "timestamp": time.time()
                    }
                    yield f"event: artifact_loading\ndata: {json.dumps(artifact_loading_data, ensure_ascii=False)}\n\n"

                # Yield parsed message as SSE event immediately
                message_data = parsed_msg.dict()
                yield f"event: message\ndata: {json.dumps(message_data, ensure_ascii=False)}\n\n"

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

            await self._cleanup_session(session_id)

        except asyncio.CancelledError:
            # Distinguish explicit user stop from client disconnect
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
                    # If client already disconnected, ignore
                    pass
                await self._cleanup_session(session_id)
                try:
                    self.stop_requests.discard(session_id)
                except Exception:
                    pass
            else:
                # Client disconnected: keep producer and cache alive; cleanup will happen on producer completion
                logger.warning(f"STOP_MANAGER: Client disconnected for {session_id}; keeping run active")
                return

        except Exception as e:
            logger.error(f"STOP_MANAGER: Error in stream_to_frontend for session {session_id}: {e}")
            await self._cleanup_session(session_id)
            raise

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

            # Clean up message queues
            if session_id in instance.message_queues:
                instance.message_queues.pop(session_id)

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
                session_id in instance.message_queues)

    # Legacy compatibility methods
    @staticmethod
    async def register_task(session_id: str, task: asyncio.Task):
        """Legacy compatibility - now handled internally"""
        pass

    @staticmethod
    async def cancel_task(session_id: str) -> bool:
        """Legacy compatibility - delegate to stop_stream"""
        return await StopManager.stop_stream(session_id)

    @staticmethod
    async def cleanup_task(session_id: str):
        """Legacy compatibility - now handled internally"""
        pass

    @staticmethod
    async def is_task_active(session_id: str) -> bool:
        """Legacy compatibility - delegate to is_stream_active"""
        return await StopManager.is_stream_active(session_id)
