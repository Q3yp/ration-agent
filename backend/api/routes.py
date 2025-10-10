import asyncio
import json
import logging
import time
import io
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from langchain_core.messages import HumanMessage
import pandas as pd
from models import (
    ChatRequest, FileUploadResponse, FileDeleteResponse,
    SessionCreateRequest, SessionCreateResponse, SessionStatsResponse,
    ParsedMessage, FeedbaseListResponse, FeedbaseResponse,
    FeedbaseUpdateRequest, FeedbaseDeleteResponse, FeedbaseData,
    AnimalType
)
from services.session_manager import session_manager
from services.chat_history_service import chat_history_service
from utils.model_config import get_model_config
from utils.prompt_loader import env
from utils.stop_manager import StopManager
from auth.config import current_active_user
from auth.models import User


router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def generate_title_for_session(session_id: str, user_message: str, title_queue: asyncio.Queue):
    """Background task to generate title for session based on first user message"""
    # Truncate message if too long for title generation
    preview = user_message[:500] if len(user_message) > 500 else user_message

    # Get the title generation model
    model = get_model_config("title_generation")

    # Load and render the title generation prompt template
    template = env.get_template("title_generation.md")
    title_prompt = template.render(user_message=preview)

    # Generate title using the model
    response = await model.ainvoke(title_prompt)

    # Extract and clean the title
    generated_title = response.content.strip()

    # Remove any quotes or extra formatting
    generated_title = generated_title.replace('"', '').replace("'", "").strip()

    # Ensure title doesn't exceed 60 characters
    if len(generated_title) > 60:
        generated_title = generated_title[:57] + "..."

    # Fallback title if generation fails
    if not generated_title or len(generated_title) < 3:
        generated_title = "New Conversation"

    # Update the session title and mark as generated
    await session_manager.update_session_title(session_id, generated_title)
    await session_manager.mark_title_generated(session_id)

    logger.info(f"Generated title for session {session_id}: {generated_title}")

    # Send title update through the chat stream
    await title_queue.put(generated_title)


# easier to filter health check logs
@router.get("/health", response_class=JSONResponse)
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@router.get("/", response_class=JSONResponse)
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}


@router.get("/health", response_class=JSONResponse)
async def health():
    """Health check endpoint with detailed status"""
    active_sessions = await session_manager.list_active_sessions()
    return {
        "status": "healthy",
        "agent_ready": True,  # Agents are created on-demand
        "active_connections": 0,
        "active_sessions": len(active_sessions),
        "timestamp": time.time()
    }


@router.post("/sessions/create", response_model=SessionCreateResponse)
async def create_session(
    request: SessionCreateRequest,
    current_user: User = Depends(current_active_user)
):
    """Create a new session with workspace and agent context"""
    try:
        # Validate user has permission for this animal_type
        if current_user.allowed_animal_types:
            if request.animal_type not in current_user.allowed_animal_types:
                raise HTTPException(
                    status_code=403,
                    detail=f"User does not have permission for animal type '{request.animal_type}'"
                )

        session_context = await session_manager.create_session(
            request.session_id,
            str(current_user.id),
            request.animal_type
        )

        return {
            "session_id": session_context.session_id,
            "workspace_path": session_context.workspace_path,
            "created_at": session_context.created_at.isoformat(),
            "message": f"Session '{request.session_id}' created successfully",
            "title": session_context.title,
            "animal_type": session_context.animal_type
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/sessions/{session_id}/stats", response_model=SessionStatsResponse)
async def get_session_stats(
    session_id: str,
    current_user: User = Depends(current_active_user)
):
    """Get session statistics and metadata"""
    stats = await session_manager.get_session_stats(session_id)
    return stats


@router.get("/sessions/list")
async def list_sessions(current_user: User = Depends(current_active_user)):
    """List user's active sessions"""
    active_sessions = await session_manager.list_user_sessions(str(current_user.id))
    return {
        "active_sessions": active_sessions,
        "total_count": len(active_sessions)
    }


@router.get("/animal-types")
async def get_animal_types(current_user: User = Depends(current_active_user)):
    """Get list of animal types available to the current user"""
    # If user has specific allowed types, return those
    if current_user.allowed_animal_types:
        allowed_types = current_user.allowed_animal_types
    else:
        # If no restrictions, return all available types
        allowed_types = [t.value for t in AnimalType]

    # Build response with display names
    animal_type_options = [
        {
            "value": animal_type,
            "label": AnimalType.get_display_name(animal_type)
        }
        for animal_type in allowed_types
    ]

    return {
        "animal_types": animal_type_options
    }


@router.delete("/sessions/delete-all")
async def delete_all_sessions(current_user: User = Depends(current_active_user)):
    """Soft delete all user sessions - marks as deleted but preserves data and history"""
    try:
        # Use soft delete to preserve conversation history and data
        result = await session_manager.soft_delete_user_sessions(str(current_user.id))

        return {}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete all sessions: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(current_active_user)
):
    """Soft delete a session - marks as deleted but preserves data and history"""
    session_stats = await session_manager.get_session_stats(session_id)
    if not session_stats["exists"]:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # Use soft delete to preserve conversation history and data
        await session_manager.soft_delete_session(session_id)

        return {}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    request: Request,
    current_user: User = Depends(current_active_user)
):
    """History endpoint with dual behavior:
    - JSON (default): return full persisted history and summary
    - SSE (Accept: text/event-stream): stream history first, then if a run is active
      replay cached live events and tail until completion, otherwise end after history
    """
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")

    accept = (request.headers.get("accept") or "").lower()
    if "text/event-stream" not in accept:
        # JSON response (backward-compatible)
        try:
            raw_messages, summary = await chat_history_service.get_session_data(session_id)
            logger.info(f"API: Retrieved {len(raw_messages)} raw messages for session {session_id}")
            session_parser = session_manager.get_session_parser(session_id)
            parsed_messages = session_parser.parse_messages(raw_messages)
            logger.info(f"API: Parsed into {len(parsed_messages)} messages for session {session_id}")
            messages_for_frontend = [msg.dict() for msg in parsed_messages]
            logger.info(f"API: Returning {len(messages_for_frontend)} messages to frontend for session {session_id}")
            return {
                "session_id": session_id,
                "messages": messages_for_frontend,
                "summary": summary
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get session history: {str(e)}")

    # SSE response: stream history + (if active) live tail
    async def generate_history_stream():
        # Anti-buffer padding
        yield f": {' ' * 2048}\n\n"
        current_message_id = f"{session_id}_{int(time.time() * 1000000)}"

        # Determine mode
        is_active = await StopManager.is_stream_active(session_id)
        mode = "stream" if is_active else "history"

        # Connected event
        yield (
            "event: connected\n"
            f"data: {json.dumps({'message_id': current_message_id, 'session_id': session_id, 'mode': mode})}\n\n"
        )

        # Load persisted history and stream it first
        raw_messages, _summary = await chat_history_service.get_session_data(session_id)
        session_parser = session_manager.get_session_parser(session_id)
        parsed_messages = session_parser.parse_messages(raw_messages)
        last_ts = 0.0
        for msg in parsed_messages:
            ts = msg.timestamp or time.time()
            last_ts = max(last_ts, ts)
            yield f"event: message\ndata: {json.dumps(msg.dict(), ensure_ascii=False)}\n\n"

        if not is_active:
            # No active run - end stream after history
            completion_data = {
                "type": "agent_complete",
                "message_id": current_message_id,
                "timestamp": time.time(),
            }
            yield f"event: complete\ndata: {json.dumps(completion_data, ensure_ascii=False)}\n\n"
            return

        # Active run - replay cached live events since last history timestamp, then tail
        stop_manager = StopManager.get_instance()
        parser = session_parser

        cached = list(stop_manager.active_sessions.get(session_id, []))
        # Replay only events newer than last history timestamp to minimize duplicates
        for ev in cached:
            try:
                if ev.get("timestamp", 0) <= last_ts:
                    continue
                for msg in parser.parse_streaming_event(ev):
                    yield f"event: message\ndata: {json.dumps(msg.dict(), ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"HISTORY_SSE: Error replaying cached event: {e}")
                continue

        cursor = len(cached)
        idle = 0
        while True:
            if session_id not in stop_manager.active_sessions:
                break
            events = stop_manager.active_sessions.get(session_id, [])
            if cursor < len(events):
                for ev in events[cursor:]:
                    try:
                        for msg in parser.parse_streaming_event(ev):
                            yield f"event: message\ndata: {json.dumps(msg.dict(), ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.error(f"HISTORY_SSE: Error parsing tailed event: {e}")
                        continue
                cursor = len(events)
                idle = 0
            else:
                idle += 1
                if idle % 10 == 0:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0.2)

        completion_data = {
            "type": "agent_complete",
            "message_id": current_message_id,
            "timestamp": time.time(),
        }
        yield f"event: complete\ndata: {json.dumps(completion_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_history_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "Access-Control-Expose-Headers": "Content-Type",
            "X-Proxy-Buffer": "no",
            "Vary": "Accept",
        },
    )







@router.get("/chat/status/{session_id}", response_class=JSONResponse)
async def chat_status(
    session_id: str,
    current_user: User = Depends(current_active_user)
):
    """Return whether this session should be treated as live stream (resume/replay) or history.
    - mode = "stream" when StopManager has an active stream lifecycle for this session
    - mode = "history" otherwise
    """
    # Verify session exists
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check StopManager for active stream state
    try:
        is_active = await StopManager.is_stream_active(session_id)
    except Exception:
        is_active = False

    return {
        "session_id": session_id,
        "mode": "stream" if is_active else "history",
        "stream_active": is_active,
        "timestamp": time.time(),
    }



@router.post("/chat/stop/{session_id}")
async def stop_chat(
    session_id: str,
    current_user: User = Depends(current_active_user)
):
    """Request stop for an active chat session"""
    logger.info(f"STOP: Stop request received for session {session_id}")

    # Verify session exists
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        logger.error(f"STOP: Session {session_id} not found for stop request")
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # Cancel the active task immediately
        logger.info(f"STOP: Cancelling task for session {session_id}")
        stop_manager = StopManager.get_instance()
        cancelled = await stop_manager.stop_stream(session_id)

        if cancelled:
            logger.info(f"STOP: Task cancelled successfully for session {session_id}")
            return {
                "message": "Execution stopped",
                "session_id": session_id,
                "timestamp": time.time(),
                "note": "Task cancelled immediately"
            }
        else:
            logger.info(f"STOP: No active task found for session {session_id}")
            return {
                "message": "No active execution to stop",
                "session_id": session_id,
                "timestamp": time.time()
            }

    except Exception as e:
        logger.error(f"STOP: Failed to stop session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop session: {str(e)}")


@router.post("/chat/stream/{session_id}")
async def stream_chat(
    session_id: str,
    request: ChatRequest,
    current_user: User = Depends(current_active_user)
):
    """HTTP Server-Sent Events streaming endpoint for real-time chat"""
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Get session (must exist) and create agent
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found. Create session first.")

    # Create title queue for single stream approach
    title_queue = asyncio.Queue()

    # Start title generation immediately if this is the first message
    if not session_context.title_generated:
        asyncio.create_task(generate_title_for_session(session_id, user_message, title_queue))

    try:
        session_agent = await session_manager.get_session_agent(session_id)
    except RuntimeError as e:
        logger.error(f"Failed to get agent for session {session_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))

    async def generate_sse_stream():
        """Delegate stream generation to StopManager"""
        # Import agent configuration for recursion limit
        from utils.model_config import get_agent_config
        agent_config = get_agent_config()

        config = {
            "configurable": {
                "thread_id": session_id,
                "user_id": str(current_user.id)  # Add user_id for store operations
            },
            "recursion_limit": agent_config["recursion_limit"]
        }

        # Add user message to appropriate thread based on workflow stage
        user_msg = HumanMessage(content=user_message)

        # Get current state to check workflow_stage
        try:
            current_state = await session_agent.aget_state(config)
            workflow_stage = current_state.values.get("workflow_stage") if current_state.values else None
            logger.info(f"ROUTES: Current workflow_stage: {workflow_stage}")

            # Add to main messages - pre_model_hook will route to appropriate thread
            agent_input = {"messages": [user_msg]}
        except Exception as e:
            logger.error(f"ROUTES: Failed to get state, defaulting to messages: {e}")
            agent_input = {"messages": [user_msg]}

        # Use StopManager as true middleware - direct streaming to frontend
        stop_manager = StopManager.get_instance()
        logger.error(f"ROUTES_DEBUG: About to call stream_to_frontend for {session_id}")
        try:
            async for event in stop_manager.stream_to_frontend(
                session_id, session_agent, agent_input, config, title_queue
            ):
                yield event
        except Exception as e:
            logger.error(f"STREAM: Error in SSE stream for session {session_id}: {e}")
            current_message_id = f"{session_id}_{int(time.time() * 1000000)}"
            error_data = {
                "type": "error",
                "content": f"Error processing message: {str(e)}",
                "error_code": "PROCESSING_ERROR",
                "message_id": current_message_id,
                "timestamp": time.time()
            }
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_sse_stream(),
        media_type="text/event-stream",
        headers={
            # Prevent intermediate proxies/CDNs from transforming or buffering
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Explicit content type with charset for some proxies
            "Content-Type": "text/event-stream; charset=utf-8",
            # Nginx: honor this to disable proxy buffering per response
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            # CORS: allow frontend to connect
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "Access-Control-Expose-Headers": "Content-Type",
            # Custom hint header for non-nginx proxies
            "X-Proxy-Buffer": "no",
            # Help caches/proxies vary on Accept header (SSE vs JSON)
            "Vary": "Accept"
        }
    )



@router.get("/chat/stream/{session_id}/resume")
async def resume_stream(
    session_id: str,
    current_user: User = Depends(current_active_user)
):
    """
    Attach to an active stream: replay cached events and then tail new events until the run finishes.
    If there is no active run, return 404 so the frontend can load history.
    """
    # Verify session exists
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")

    stop_manager = StopManager.get_instance()

    # Ensure there's an active run to resume
    is_active = await StopManager.is_stream_active(session_id)
    if not is_active or session_id not in stop_manager.active_sessions:
        raise HTTPException(status_code=404, detail="No active stream to resume")

    async def generate_resume_stream():
        # Anti-buffer padding
        yield f": {' ' * 2048}\n\n"
        # Connected event (resume)
        current_message_id = f"{session_id}_{int(time.time() * 1000000)}"
        yield (
            "event: connected\n"
            f"data: {json.dumps({'message_id': current_message_id, 'session_id': session_id, 'mode': 'stream'})}\n\n"
        )

        parser = session_manager.get_session_parser(session_id)
        artifact_loading_sent = False

        # Replay cached events
        cached = list(stop_manager.active_sessions.get(session_id, []))
        for cached_event in cached:
            try:
                parsed_messages = parser.parse_streaming_event(cached_event)
                for msg in parsed_messages:
                    # Optional: send artifact loading hint once
                    if (
                        msg.type == "agent"
                        and "create_artifact" in msg.content
                        and not artifact_loading_sent
                    ):
                        artifact_loading_sent = True
                        yield (
                            "event: artifact_loading\n"
                            f"data: {json.dumps({'type': 'artifact_loading', 'message_id': current_message_id, 'timestamp': time.time()}, ensure_ascii=False)}\n\n"
                        )

                    yield f"event: message\ndata: {json.dumps(msg.dict(), ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"RESUME: Error replaying cached event: {e}")
                continue

        # Tail new events by polling the active_sessions buffer
        cursor = len(cached)
        idle_heartbeats = 0
        while True:
            # If the session was cleaned up, complete the stream
            if session_id not in stop_manager.active_sessions:
                break

            events = stop_manager.active_sessions.get(session_id, [])
            if cursor < len(events):
                for ev in events[cursor:]:
                    try:
                        parsed_messages = parser.parse_streaming_event(ev)
                        for msg in parsed_messages:
                            yield f"event: message\ndata: {json.dumps(msg.dict(), ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.error(f"RESUME: Error parsing live-tailed event: {e}")
                        continue
                cursor = len(events)
                idle_heartbeats = 0
            else:
                # Send heartbeat every ~10 iterations (~2s) to defeat buffering
                idle_heartbeats += 1
                if idle_heartbeats % 10 == 0:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0.2)

        # Completed
        completion_data = {
            "type": "agent_complete",
            "message_id": current_message_id,
            "timestamp": time.time(),
        }
        yield f"event: complete\ndata: {json.dumps(completion_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_resume_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "Access-Control-Expose-Headers": "Content-Type",
            "X-Proxy-Buffer": "no",
            "Vary": "Accept",
        },
    )



@router.post("/files/upload/{session_id}", response_model=FileUploadResponse)
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(current_active_user)
):
    """Upload a file to the session's workspace"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Security checks
    max_file_size = 10 * 1024 * 1024  # 10MB
    allowed_extensions = {'.txt', '.py', '.js', '.json', '.csv', '.md', '.html', '.css', '.xml', '.yaml', '.yml', '.xlsx'}

    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"File type {file_extension} not allowed")

    # Get session (must exist) and get workspace
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found. Create session first.")

    workspace_dir = session_context.workspace_path

    file_path = Path(workspace_dir) / file.filename

    try:
        # Read and validate file size
        content = await file.read()
        if len(content) > max_file_size:
            raise HTTPException(status_code=400, detail="File too large")

        # Write file to workspace
        with open(file_path, "wb") as f:
            f.write(content)

        return {
            "message": f"File '{file.filename}' uploaded successfully",
            "filename": file.filename,
            "size": len(content),
            "session_id": session_id,
            "path": str(file_path.relative_to(Path(workspace_dir)))
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")




@router.delete("/files/delete/{session_id}/{filename}", response_model=FileDeleteResponse)
async def delete_file(
    session_id: str,
    filename: str,
    current_user: User = Depends(current_active_user)
):
    """Delete a file from the session's workspace"""
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")

    workspace_dir = Path(session_context.workspace_path)
    file_path = workspace_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.is_relative_to(workspace_dir):
        raise HTTPException(status_code=400, detail="Invalid file path")

    try:
        file_path.unlink()
        return {
            "message": f"File '{filename}' deleted successfully",
            "session_id": session_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.get("/files/download/{session_id}/{filename}")
async def download_file(
    session_id: str,
    filename: str,
    current_user: User = Depends(current_active_user)
):
    """Download a file from the session's workspace"""
    from urllib.parse import unquote

    # URL-decode the filename to handle Chinese characters
    decoded_filename = unquote(filename)

    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")

    workspace_dir = Path(session_context.workspace_path)
    file_path = workspace_dir / decoded_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.is_relative_to(workspace_dir):
        raise HTTPException(status_code=400, detail="Invalid file path")

    try:
        # Determine media type based on file extension
        media_type = "application/octet-stream"
        if file_path.suffix.lower() == '.xlsx':
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif file_path.suffix.lower() == '.csv':
            media_type = "text/csv"
        elif file_path.suffix.lower() == '.json':
            media_type = "application/json"
        elif file_path.suffix.lower() == '.txt':
            media_type = "text/plain"

        # Encode filename for Content-Disposition header (RFC 5987)
        from urllib.parse import quote
        encoded_filename = quote(decoded_filename.encode('utf-8'))

        return FileResponse(
            path=str(file_path),
            filename=decoded_filename,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


# Feedbase Management Endpoints

@router.get("/feedbases/list", response_model=FeedbaseListResponse)
async def list_feedbases(current_user: User = Depends(current_active_user)):
    """List all feedbases for the current user"""
    try:
        from core.agent import _connection_manager

        # Get shared store instance
        store = await _connection_manager.get_shared_store()
        user_id = str(current_user.id)
        namespace = ("feedbases", user_id)

        # Get all feedbases for this user
        feedbase_entries = await store.asearch(namespace)
        feedbase_names = []

        for entry in feedbase_entries:
            # Extract feedbase name from namespace tuple
            if len(entry.namespace) >= 3:
                feedbase_name = entry.namespace[2]  # ("feedbases", user_id, feedbase_name)
                if feedbase_name not in feedbase_names:
                    feedbase_names.append(feedbase_name)

        return FeedbaseListResponse(feedbases=sorted(feedbase_names))

    except Exception as e:
        logger.error(f"Error listing feedbases for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list feedbases: {str(e)}")


@router.get("/feedbases/{feedbase_name}", response_model=FeedbaseResponse)
async def get_feedbase(feedbase_name: str, current_user: User = Depends(current_active_user)):
    """Get feedbase details by name"""
    try:
        from core.agent import _connection_manager

        # Get shared store instance
        store = await _connection_manager.get_shared_store()
        user_id = str(current_user.id)
        namespace = ("feedbases", user_id, feedbase_name)

        # Get feedbase data
        result = await store.aget(namespace, "data")

        if not result:
            raise HTTPException(status_code=404, detail=f"Feedbase '{feedbase_name}' not found")

        # Validate and return feedbase data
        feedbase_data = FeedbaseData(**result.value)
        return FeedbaseResponse(name=feedbase_name, data=feedbase_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feedbase {feedbase_name} for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get feedbase: {str(e)}")


@router.put("/feedbases/{feedbase_name}", response_model=FeedbaseResponse)
async def update_feedbase(
    feedbase_name: str,
    request: FeedbaseUpdateRequest,
    current_user: User = Depends(current_active_user)
):
    """Update or create a feedbase"""
    try:
        from core.agent import _connection_manager

        # Get shared store instance
        store = await _connection_manager.get_shared_store()
        user_id = str(current_user.id)
        namespace = ("feedbases", user_id, feedbase_name)

        # Store the feedbase data
        feedbase_dict = request.data.model_dump()
        await store.aput(namespace, "data", feedbase_dict)

        logger.info(f"Updated feedbase {feedbase_name} for user {current_user.id}")
        return FeedbaseResponse(name=feedbase_name, data=request.data)

    except Exception as e:
        logger.error(f"Error updating feedbase {feedbase_name} for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update feedbase: {str(e)}")


@router.delete("/feedbases/{feedbase_name}", response_model=FeedbaseDeleteResponse)
async def delete_feedbase(feedbase_name: str, current_user: User = Depends(current_active_user)):
    """Delete a feedbase"""
    try:
        from core.agent import _connection_manager

        # Get shared store instance
        store = await _connection_manager.get_shared_store()
        user_id = str(current_user.id)
        namespace = ("feedbases", user_id, feedbase_name)

        # Check if feedbase exists
        result = await store.aget(namespace, "data")
        if not result:
            raise HTTPException(status_code=404, detail=f"Feedbase '{feedbase_name}' not found")

        # Delete the feedbase
        await store.adelete(namespace, "data")

        logger.info(f"Deleted feedbase {feedbase_name} for user {current_user.id}")
        return FeedbaseDeleteResponse(
            message=f"Feedbase '{feedbase_name}' deleted successfully",
            feedbase_name=feedbase_name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting feedbase {feedbase_name} for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete feedbase: {str(e)}")


@router.get("/feedbases/{feedbase_name}/export")
async def export_feedbase(feedbase_name: str, current_user: User = Depends(current_active_user)):
    """Export feedbase as Excel file"""
    try:
        from core.agent import _connection_manager

        # Get shared store instance
        store = await _connection_manager.get_shared_store()
        user_id = str(current_user.id)
        namespace = ("feedbases", user_id, feedbase_name)

        # Get feedbase data
        result = await store.aget(namespace, "data")
        if not result:
            raise HTTPException(status_code=404, detail=f"Feedbase '{feedbase_name}' not found")

        # Parse the feedbase data
        if hasattr(result, 'value'):
            # If result has a value attribute, it might be a string that needs parsing
            feedbase_data = json.loads(result.value) if isinstance(result.value, str) else result.value
        else:
            # If result doesn't have a value attribute, use the result directly
            feedbase_data = result

        # Handle case where feedbase_data might still be a string
        if isinstance(feedbase_data, str):
            feedbase_data = json.loads(feedbase_data)

        feeds = feedbase_data.get('feeds', {})

        # Prepare data for Excel export
        rows = []
        for feed_name, feed_data in feeds.items():
            row = {
                '饲料名称': feed_name,
                '干物质含量(%)': feed_data.get('dm_percent', 0),
                '成本(¥/kg)': feed_data.get('cost_per_kg', 0)
            }

            # Add nutrients as separate columns
            nutrients = feed_data.get('nutrients', {})
            for nutrient_name, nutrient_value in nutrients.items():
                row[nutrient_name] = nutrient_value

            rows.append(row)

        # Create DataFrame and Excel file
        if not rows:
            # Create empty DataFrame with basic structure
            df = pd.DataFrame(columns=['饲料名称', '干物质含量(%)', '成本(¥/kg)'])
        else:
            df = pd.DataFrame(rows)

        # Create Excel file in memory
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Feedbase', index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets['Feedbase']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width

        excel_buffer.seek(0)

        # Create filename with proper encoding for international characters
        import urllib.parse

        # Create a safe ASCII filename as fallback
        safe_feedbase_name = "".join(c for c in feedbase_name if c.isascii() and (c.isalnum() or c in (' ', '-', '_'))).strip()
        if not safe_feedbase_name:
            safe_feedbase_name = "feedbase"
        ascii_filename = f"{safe_feedbase_name}.xlsx"

        # Create properly encoded filename for UTF-8 support
        utf8_filename = f"{feedbase_name}.xlsx"
        encoded_filename = urllib.parse.quote(utf8_filename.encode('utf-8'))

        # Return file response with proper Content-Disposition header
        return StreamingResponse(
            io.BytesIO(excel_buffer.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={ascii_filename}; filename*=UTF-8''{encoded_filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting feedbase {feedbase_name} for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export feedbase: {str(e)}")