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
    SessionCreateRequest, SessionCreateResponse, SessionStatsResponse
)
from session_manager import session_manager
from message_processor import (
    process_tool_start_event, process_tool_end_event, process_chat_model_stream_event,
    save_conversation_messages, get_conversation_context
)
from chat_history_service import chat_history_service


router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@router.get("/", response_class=JSONResponse)
async def root():
    """Health check endpoint"""
    return {"message": "LangGraph ReAct Agent API is running!", "version": "0.1.0"}


@router.get("/health", response_class=JSONResponse)
async def health():
    """Health check endpoint with detailed status"""
    return {
        "status": "healthy", 
        "agent_ready": session_manager._sessions and all(
            session_manager.get_session_stats(sid).get("agent_ready", False) 
            for sid in session_manager._active_sessions
        ) if session_manager._active_sessions else True,
        "active_connections": 0,
        "active_sessions": len(session_manager._active_sessions),
        "timestamp": asyncio.get_event_loop().time()
    }


@router.post("/sessions/create", response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new session with workspace and agent context"""
    try:
        session_context = session_manager.create_session(request.session_id)
        
        return {
            "session_id": session_context.session_id,
            "workspace_path": session_context.workspace_path,
            "created_at": session_context.created_at.isoformat(),
            "message": f"Session '{request.session_id}' created successfully"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/sessions/{session_id}/stats", response_model=SessionStatsResponse)
async def get_session_stats(session_id: str):
    """Get session statistics and metadata"""
    stats = session_manager.get_session_stats(session_id)
    return stats


@router.get("/sessions/list")
async def list_sessions():
    """List all active sessions"""
    return {
        "active_sessions": session_manager.list_active_sessions(),
        "total_count": len(session_manager._active_sessions)
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, remove_files: bool = False):
    """Delete a session and optionally its workspace files"""
    session_stats = session_manager.get_session_stats(session_id)
    if not session_stats["exists"]:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Clear chat history from PostgreSQL
        chat_history_service.clear_session_history(session_id)
        
        # Clean up session workspace
        session_manager.cleanup_session(session_id, remove_files=remove_files)
        
        return {
            "message": f"Session '{session_id}' deleted successfully",
            "files_removed": remove_files,
            "chat_history_cleared": True
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 50):
    """Get chat history for a session"""
    session_context = session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        if limit and limit > 0:
            messages = chat_history_service.get_recent_messages(session_id, limit)
        else:
            messages = chat_history_service.get_session_history(session_id)
        
        # Convert messages to serializable format
        history = []
        for msg in messages:
            history.append({
                "type": msg.__class__.__name__.lower().replace("message", ""),
                "content": msg.content,
                "timestamp": getattr(msg, "additional_kwargs", {}).get("timestamp")
            })
        
        summary = chat_history_service.get_session_summary(session_id)
        
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
    session_context = session_manager.get_session(session_id)
    if not session_context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        chat_history_service.clear_session_history(session_id)
        return {
            "message": f"Chat history for session '{session_id}' cleared successfully",
            "session_id": session_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session history: {str(e)}")


@router.post("/chat/stream/{session_id}")
async def stream_chat(session_id: str, request: ChatRequest):
    """HTTP Server-Sent Events streaming endpoint for real-time chat"""
    logger.info(f"Starting chat stream for session: {session_id}")
    user_message = request.message.strip()
    if not user_message:
        logger.warning(f"Empty message received for session: {session_id}")
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    logger.debug(f"User message: {user_message[:100]}..." if len(user_message) > 100 else f"User message: {user_message}")
    
    # Get session (must exist) and create agent
    logger.debug(f"Getting session context for: {session_id}")
    session_context = session_manager.get_session(session_id)
    if not session_context:
        logger.error(f"Session {session_id} not found")
        raise HTTPException(status_code=404, detail="Session not found. Create session first.")
    
    logger.debug(f"Session context found, getting agent for: {session_id}")
    try:
        session_agent = await session_manager.get_session_agent(session_id)
        logger.info(f"Agent ready for session: {session_id}")
    except RuntimeError as e:
        logger.error(f"Failed to get agent for session {session_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    
    async def generate_sse_stream():
        """Generate Server-Sent Events stream following SSE specification"""
        logger.info(f"Starting SSE stream generation for session: {session_id}")
        config = {"configurable": {"thread_id": session_id}}
        current_message_id = f"{session_id}_{int(asyncio.get_event_loop().time() * 1000000)}"
        accumulated_content = ""
        tool_calls_processed = set()
        
        try:
            logger.debug(f"Sending connected event for session: {session_id}")
            yield f"event: connected\ndata: {json.dumps({'message_id': current_message_id, 'session_id': session_id})}\n\n"
            
            logger.debug(f"Sending thinking event for session: {session_id}")
            yield f"event: thinking\ndata: {json.dumps({'type': 'agent_thinking', 'message_id': current_message_id})}\n\n"
            
            logger.info(f"Starting agent.astream_events for session: {session_id}")
            async for event in session_agent.astream_events(
                {"messages": [HumanMessage(content=user_message)]},
                config=config,
                version="v2"
            ):
                logger.debug(f"Received event: {event['event']} for session: {session_id}")
                if event["event"] == "on_chat_model_stream":
                    chunk_content = event["data"]["chunk"].content
                    if chunk_content:
                        accumulated_content += chunk_content
                        
                        chunk_data = {
                            "type": "agent_chunk",
                            "content": chunk_content,
                            "message_id": current_message_id,
                            "full_content": accumulated_content,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        yield f"event: chunk\ndata: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                
                elif event["event"] == "on_tool_start":
                    try:
                        logger.debug(f"Processing on_tool_start event: {event}")
                        
                        # Add timestamp to event for processor
                        event_with_timestamp = {**event, "timestamp": asyncio.get_event_loop().time()}
                        tool_data = process_tool_start_event(event_with_timestamp)
                        
                        logger.debug(f"tool_data created: {tool_data}")
                        logger.debug(f"tool_data types: {[(k, type(v)) for k, v in tool_data.items()]}")
                        
                        json_str = json.dumps(tool_data, ensure_ascii=False)
                        yield f"event: tool_call\ndata: {json_str}\n\n"
                    except Exception as e:
                        logger.error(f"Error in on_tool_start serialization: {e}")
                        logger.error(f"Event data: {event}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                
                elif event["event"] == "on_tool_end":
                    try:
                        logger.debug(f"Processing on_tool_end event: {event}")
                        
                        # Add timestamp to event for processor
                        event_with_timestamp = {**event, "timestamp": asyncio.get_event_loop().time()}
                        tool_result_data = process_tool_end_event(event_with_timestamp)
                        
                        logger.debug(f"tool_result_data created: {tool_result_data}")
                        logger.debug(f"tool_result_data types: {[(k, type(v)) for k, v in tool_result_data.items()]}")
                        
                        json_str = json.dumps(tool_result_data, ensure_ascii=False)
                        yield f"event: tool_result\ndata: {json_str}\n\n"
                    except Exception as e:
                        logger.error(f"Error in on_tool_end serialization: {e}")
                        logger.error(f"Event data: {event}")
                        logger.error(f"Tool output type: {type(event['data']['output'])}")
                        logger.error(f"Tool output value: {event['data']['output']}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
            
            logger.info(f"Agent stream completed for session: {session_id}")
            # Save conversation to persistent history
            try:
                save_conversation_messages(session_id, user_message, accumulated_content)
                logger.debug(f"Conversation saved for session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to save conversation history: {e}")
            
            completion_data = {
                "type": "agent_complete",
                "message_id": current_message_id,
                "timestamp": asyncio.get_event_loop().time()
            }
            logger.debug(f"Sending completion event for session: {session_id}")
            yield f"event: complete\ndata: {json.dumps(completion_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"Error in SSE stream for session {session_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
    session_context = session_manager.get_session(session_id)
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
    session_context = session_manager.get_session(session_id)
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
    session_context = session_manager.get_session(session_id)
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