import asyncio
import json
import logging
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from langchain_core.messages import HumanMessage
from models import (
    ChatRequest, FileUploadResponse, FileDeleteResponse,
    SessionCreateRequest, SessionCreateResponse, SessionStatsResponse,
    ParsedMessage
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
        session_context = await session_manager.create_session(request.session_id, str(current_user.id))
        
        return {
            "session_id": session_context.session_id,
            "workspace_path": session_context.workspace_path,
            "created_at": session_context.created_at.isoformat(),
            "message": f"Session '{request.session_id}' created successfully",
            "title": session_context.title
        }
    
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
    current_user: User = Depends(current_active_user)
):
    """Get chat history for a session"""
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Get complete messages from supervisor and all worker subgraphs
        raw_messages = await chat_history_service.get_complete_session_messages(session_id)
        logger.info(f"API: Retrieved {len(raw_messages)} raw messages for session {session_id}")
        
        # Use session-specific parser for consistent formatting
        session_parser = session_manager.get_session_parser(session_id)
        parsed_messages = session_parser.parse_messages(raw_messages)
        logger.info(f"API: Parsed into {len(parsed_messages)} messages for session {session_id}")
        
        # Convert to dict format for JSON serialization
        messages_for_frontend = [msg.dict() for msg in parsed_messages]
        logger.info(f"API: Returning {len(messages_for_frontend)} messages to frontend for session {session_id}")
        
        # Get summary
        summary = await chat_history_service.get_session_summary_async(session_id)
        
        return {
            "session_id": session_id,
            "messages": messages_for_frontend,
            "summary": summary
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session history: {str(e)}")








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
        cancelled = await StopManager.cancel_task(session_id)
        
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
        """Generate Server-Sent Events stream following SSE specification"""
        # Import agent configuration for recursion limit
        from utils.model_config import get_agent_config
        agent_config = get_agent_config()

        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": agent_config["recursion_limit"]
        }

        logger.info(f"Starting agent stream for session {session_id} with recursion_limit={agent_config['recursion_limit']}")
        current_message_id = f"{session_id}_{int(time.time() * 1000000)}"
        accumulated_content = ""
        tool_calls_processed = set()
        artifact_loading_sent = False

        try:
            yield f"event: connected\ndata: {json.dumps({'message_id': current_message_id, 'session_id': session_id})}\n\n"

            # Register current task for cancellation support
            current_task = asyncio.current_task()
            await StopManager.register_task(session_id, current_task)

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

            # Create async iterator for agent events with subgraph streaming
            agent_events = session_agent.astream_events(
                agent_input,
                config=config,
                subgraphs=True
            )

            # Get session parser from session manager (persistent across events)
            session_parser = session_manager.get_session_parser(session_id)
            logger.info(f"STREAM: Using persistent message parser for session {session_id}")

            # Process both agent events and title updates concurrently
            async for event in agent_events:
                
                # Check for title updates first (non-blocking)
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
                    pass  # No title update available

                # Process agent event using session-specific parser
                try:
                    # Add timestamp to event
                    event_with_timestamp = {**event, "timestamp": time.time()}
                    
                    # Parse event into ParsedMessage format
                    parsed_messages = session_parser.parse_streaming_event(event_with_timestamp)
                    
                    # Send each ParsedMessage as SSE event
                    for parsed_msg in parsed_messages:
                        # Handle artifact loading detection for agent messages
                        if parsed_msg.type == "agent" and "create_artifact" in parsed_msg.content and not artifact_loading_sent:
                            artifact_loading_sent = True
                            artifact_loading_data = {
                                "type": "artifact_loading",
                                "message_id": current_message_id,
                                "timestamp": time.time()
                            }
                            yield f"event: artifact_loading\ndata: {json.dumps(artifact_loading_data, ensure_ascii=False)}\n\n"
                        
                        # Send ParsedMessage as SSE event
                        message_data = parsed_msg.dict()
                        yield f"event: message\ndata: {json.dumps(message_data, ensure_ascii=False)}\n\n"
                        
                except Exception as e:
                    logger.error(f"Error processing streaming event: {e}")
                    # Continue without failing the entire stream
                
            
            # Note: Conversation history is automatically saved by LangGraph's checkpointer
            # No need to manually save messages as they're preserved in the graph state

            # Final check for title updates after agent completes
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
                pass  # No title update available

            completion_data = {
                "type": "agent_complete",
                "message_id": current_message_id,
                "timestamp": time.time()
            }
            yield f"event: complete\ndata: {json.dumps(completion_data, ensure_ascii=False)}\n\n"
            
        except asyncio.CancelledError:
            logger.info(f"STREAM: Task cancelled for session {session_id}")
            # This was a user-requested stop via task cancellation
            stopped_data = {
                "type": "agent_stopped", 
                "message": "Agent execution stopped by user request",
                "session_id": session_id,
                "timestamp": time.time()
            }
            yield f"event: stopped\ndata: {json.dumps(stopped_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"STREAM: Error in SSE stream for session {session_id}: {e}")
            error_data = {
                "type": "error",
                "content": f"Error processing message: {str(e)}",
                "error_code": "PROCESSING_ERROR",
                "message_id": current_message_id,
                "timestamp": time.time()
            }
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        
        finally:
            # Always cleanup the task from registry
            await StopManager.cleanup_task(session_id)
    
    return StreamingResponse(
        generate_sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "Access-Control-Expose-Headers": "Content-Type",
            "X-Proxy-Buffer": "no"
        }
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