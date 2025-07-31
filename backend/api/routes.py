import asyncio
import json
import os
import logging
import traceback
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from langchain_core.messages import HumanMessage
from models import (
    ChatRequest, FileUploadResponse, FileListResponse, FileDeleteResponse,
    SessionCreateRequest, SessionCreateResponse, SessionStatsResponse,
    SessionTitleRequest, SessionTitleResponse
)
from services.session_manager import session_manager
from utils.message_processor import (
    process_tool_start_event, process_tool_end_event, process_chat_model_stream_event
)
from services.chat_history_service import chat_history_service
from agents.nodes import StreamingResponseParser
from utils.message_parser import message_parser
from utils.model_config import get_model_config
from utils.prompt_loader import env


router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
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

    # Update the session title
    await session_manager.update_session_title(session_id, generated_title)
    session_context = await session_manager.get_session(session_id)
    if session_context:
        session_context.title_generated = True

    logger.info(f"Generated title for session {session_id}: {generated_title}")

    # Send title update through the chat stream
    await title_queue.put(generated_title)


@router.get("/", response_class=JSONResponse)
async def root():
    """Health check endpoint"""
    return {"message": "LangGraph ReAct Agent API is running!", "version": "0.1.0"}


@router.get("/health", response_class=JSONResponse)
async def health():
    """Health check endpoint with detailed status"""
    active_sessions = await session_manager.list_active_sessions()
    return {
        "status": "healthy", 
        "agent_ready": True,  # Agents are created on-demand
        "active_connections": 0,
        "active_sessions": len(active_sessions),
        "timestamp": asyncio.get_event_loop().time()
    }


@router.post("/sessions/create", response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new session with workspace and agent context"""
    try:
        session_context = await session_manager.create_session(request.session_id)
        
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
async def get_session_stats(session_id: str):
    """Get session statistics and metadata"""
    stats = await session_manager.get_session_stats(session_id)
    return stats


@router.get("/sessions/list")
async def list_sessions():
    """List all active sessions"""
    active_sessions = await session_manager.list_active_sessions()
    return {
        "active_sessions": active_sessions,
        "total_count": len(active_sessions)
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, remove_files: bool = False):
    """Soft delete a session - marks as deleted but preserves data and history"""
    session_stats = await session_manager.get_session_stats(session_id)
    if not session_stats["exists"]:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # Use soft delete to preserve conversation history and data
        await session_manager.soft_delete_session(session_id)

        # Optionally remove workspace files if requested
        if remove_files:
            session = await session_manager.get_session(session_id)
            if session:
                workspace_path = Path(session.workspace_path)
                if workspace_path.exists():
                    import shutil
                    shutil.rmtree(workspace_path)

        return {
            "message": f"Session '{session_id}' deleted successfully",
            "files_removed": remove_files,
            "chat_history_preserved": True,  # LangGraph checkpoints and session data preserved
            "note": "Session marked as deleted but conversation history and data are preserved"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 50):
    """Get chat history for a session"""
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Use the unified parser for consistent message formatting
        history = await chat_history_service.get_session_history_for_frontend_async(session_id, limit)
        summary = await chat_history_service.get_session_summary_async(session_id)
        
        return {
            "session_id": session_id,
            "messages": history,
            "summary": summary
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session history: {str(e)}")


@router.delete("/sessions/{session_id}/history")
async def clear_session_history(session_id: str):
    """Clear chat history for a session"""
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Note: LangGraph checkpoints cannot be directly cleared
        await chat_history_service.clear_session_history_async(session_id)
        return {
            "message": f"Chat history for session '{session_id}' cannot be cleared - LangGraph checkpoints are immutable",
            "session_id": session_id,
            "success": False,
            "note": "Consider using a new session ID for a fresh conversation"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session history: {str(e)}")


@router.post("/sessions/{session_id}/generate-title", response_model=SessionTitleResponse)
async def generate_session_title(session_id: str, request: SessionTitleRequest):
    """Generate a descriptive title for a session based on conversation content"""
    # Verify session exists
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Get the title generation model
        model = get_model_config("title_generation")
        
        # Load and render the title generation prompt template
        template = env.get_template("title_generation.md")
        title_prompt = template.render(user_message=request.conversation_preview)

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
        
        return SessionTitleResponse(
            session_id=session_id,
            title=generated_title,
            message="Title generated successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to generate title for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate title: {str(e)}")





@router.post("/chat/stream/{session_id}")
async def stream_chat(session_id: str, request: ChatRequest):
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
        config = {"configurable": {"thread_id": session_id}}
        current_message_id = f"{session_id}_{int(asyncio.get_event_loop().time() * 1000000)}"
        accumulated_content = ""
        tool_calls_processed = set()

        try:
            yield f"event: connected\ndata: {json.dumps({'message_id': current_message_id, 'session_id': session_id})}\n\n"
            yield f"event: thinking\ndata: {json.dumps({'type': 'agent_thinking', 'message_id': current_message_id})}\n\n"

            # Create async iterator for agent events
            agent_events = session_agent.astream_events(
                {"messages": [HumanMessage(content=user_message)]},
                config=config,
                version="v2"
            )

            # Process both agent events and title updates concurrently
            async for event in agent_events:
                # Check for title updates first (non-blocking)
                try:
                    title = title_queue.get_nowait()
                    title_data = {
                        "type": "title_update",
                        "title": title,
                        "session_id": session_id,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    yield f"event: title_update\ndata: {json.dumps(title_data, ensure_ascii=False)}\n\n"
                except asyncio.QueueEmpty:
                    pass  # No title update available

                # Process agent event
                if event["event"] == "on_chat_model_stream":
                    chunk_content = event["data"]["chunk"].content
                    if chunk_content:
                        accumulated_content += chunk_content
                        
                        # Parse the chunk using unified message parser
                        parsed_result = message_parser.parse_streaming_chunk(chunk_content)
                        
                        # Send user content to frontend (handles multiple <user> blocks)
                        if parsed_result["user_chunk"]:
                            chunk_data = {
                                "type": "agent_chunk",
                                "content": parsed_result["user_chunk"],
                                "message_id": current_message_id,
                                "full_content": parsed_result["user_message"],
                                "timestamp": asyncio.get_event_loop().time()
                            }
                            yield f"event: chunk\ndata: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                        
                        # When we detect a complete action block, emit role transition
                        if parsed_result["action_data"] and "route" in parsed_result["action_data"]:
                            role_data = {
                                "type": "role_transition",
                                "to_role": parsed_result["action_data"]["route"],
                                "message_id": current_message_id,
                                "timestamp": asyncio.get_event_loop().time()
                            }
                            yield f"event: role_transition\ndata: {json.dumps(role_data, ensure_ascii=False)}\n\n"
                
                elif event["event"] == "on_tool_start":
                    try:
                        # Add timestamp to event for processor
                        event_with_timestamp = {**event, "timestamp": asyncio.get_event_loop().time()}
                        tool_data = process_tool_start_event(event_with_timestamp)
                        
                        json_str = json.dumps(tool_data, ensure_ascii=False)
                        yield f"event: tool_call\ndata: {json_str}\n\n"
                    except Exception as e:
                        logger.error(f"Error in on_tool_start serialization: {e}")
                        raise
                
                elif event["event"] == "on_tool_end":
                    try:
                        # Add timestamp to event for processor
                        event_with_timestamp = {**event, "timestamp": asyncio.get_event_loop().time()}
                        tool_result_data = process_tool_end_event(event_with_timestamp)
                        
                        json_str = json.dumps(tool_result_data, ensure_ascii=False)
                        yield f"event: tool_result\ndata: {json_str}\n\n"
                    except Exception as e:
                        logger.error(f"Error in on_tool_end serialization: {e}")
                        raise
                
            
            # Note: Conversation history is automatically saved by LangGraph's checkpointer
            # No need to manually save messages as they're preserved in the graph state

            # Final check for title updates after agent completes
            try:
                title = title_queue.get_nowait()
                title_data = {
                    "type": "title_update",
                    "title": title,
                    "session_id": session_id,
                    "timestamp": asyncio.get_event_loop().time()
                }
                yield f"event: title_update\ndata: {json.dumps(title_data, ensure_ascii=False)}\n\n"
            except asyncio.QueueEmpty:
                pass  # No title update available

            completion_data = {
                "type": "agent_complete",
                "message_id": current_message_id,
                "timestamp": asyncio.get_event_loop().time()
            }
            yield f"event: complete\ndata: {json.dumps(completion_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"Error in SSE stream for session {session_id}: {e}")
            error_data = {
                "type": "error",
                "content": f"Error processing message: {str(e)}",
                "error_code": "PROCESSING_ERROR",
                "message_id": current_message_id,
                "timestamp": asyncio.get_event_loop().time()
            }
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "Access-Control-Expose-Headers": "Content-Type"
        }
    )


@router.post("/files/upload/{session_id}", response_model=FileUploadResponse)
async def upload_file(session_id: str, file: UploadFile = File(...)):
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
    
    # Sanitize filename
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-").rstrip()
    if not safe_filename:
        safe_filename = f"uploaded_file{file_extension}"
    
    file_path = Path(workspace_dir) / safe_filename
    
    try:
        # Read and validate file size
        content = await file.read()
        if len(content) > max_file_size:
            raise HTTPException(status_code=400, detail="File too large")
        
        # Write file to workspace
        with open(file_path, "wb") as f:
            f.write(content)
        
        return {
            "message": f"File '{safe_filename}' uploaded successfully",
            "filename": safe_filename,
            "size": len(content),
            "session_id": session_id,
            "path": str(file_path.relative_to(Path(workspace_dir)))
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/files/list/{session_id}", response_model=FileListResponse)
async def list_files(session_id: str):
    """List files in the session's workspace"""
    session_context = await session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_dir = Path(session_context.workspace_path)
    
    try:
        files = []
        for file_path in workspace_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "path": str(file_path.relative_to(workspace_dir))
                })
        
        return {
            "files": files,
            "session_id": session_id,
            "workspace": str(workspace_dir)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.delete("/files/delete/{session_id}/{filename}", response_model=FileDeleteResponse)
async def delete_file(session_id: str, filename: str):
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