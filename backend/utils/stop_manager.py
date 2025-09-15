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

                    # Parse and put in queue immediately
                    parser = session_manager.get_session_parser(session_id)
                    parsed_messages = parser.parse_streaming_event(event_with_timestamp)
                    for parsed_msg in parsed_messages:
                        await queue.put(parsed_msg)

                except Exception as e:
                    logger.error(f"STOP_MANAGER: Error processing live event: {e}")
                    continue

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
