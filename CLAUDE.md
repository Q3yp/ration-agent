# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ration Agent** is a full-stack AI chat application implementing a LangGraph ReAct (Reasoning and Acting) Agent with real-time streaming capabilities. The system consists of a FastAPI backend with LangGraph agent orchestration and a Next.js frontend with TypeScript.

## Development Commands

### Backend (Python/FastAPI)
```bash
cd backend/
uv sync                    # Install dependencies using uv package manager
uv run start              # Start development server (uvicorn with reload)
```

Manual server start if needed:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (Next.js/TypeScript)
```bash
cd frontend/
npm install               # Install dependencies
npm run dev              # Start development server
npm run build            # Build for production
npm run lint             # Run ESLint
```

## Architecture Overview

### Backend Structure
- **Agent System**: `agent.py` contains `AgentManager` using OpenRouter API (DeepSeek model)
- **Session Management**: `session_manager.py` handles isolated session workspaces
- **Tools System**: `tools.py` provides bash execution and file management tools
- **API Routes**: Dual communication support (SSE streaming + WebSocket)
- **Communication**: `websocket_manager.py` manages WebSocket connections

### Frontend Structure
- **Main App**: `app/page.tsx` handles session creation and management
- **Chat Interface**: `components/ChatInterface.tsx` manages chat UI
- **SSE Communication**: `hooks/useSSEChat.ts` handles real-time streaming
- **Type System**: `types/chat.ts` defines comprehensive message types

### Key Patterns
- **Session Isolation**: Each session has dedicated workspace directory
- **Dual Protocols**: Server-Sent Events (HTTP) and WebSocket communication
- **Tool Integration**: Agent can execute bash commands and file operations
- **Memory Persistence**: LangGraph checkpointing maintains conversation state

## Environment Configuration

Required `.env` file in `backend/`:
```
OPENROUTER_API_KEY=your_api_key
OPENROUTER_MODEL=deepseek/deepseek-chat-v3-0324:free
```

Optional tracing:
```
LANGSMITH_API_KEY=your_key
LANGSMITH_TRACING=true
```

## API Endpoints

### Core Communication
- `POST /chat/stream/{session_id}` - SSE streaming chat
- `WebSocket /ws/chat/{session_id}` - WebSocket chat

### Session Management
- `POST /sessions/create` - Create session with workspace
- `DELETE /sessions/{session_id}` - Delete session

### File Management
- `POST /files/upload/{session_id}` - Upload files (10MB limit)
- `GET /files/list/{session_id}` - List session files
- Allowed extensions: `.txt`, `.py`, `.js`, `.json`, `.csv`, `.md`, `.html`, `.css`, `.xml`, `.yaml`, `.yml`, `.xlsx`

## Development Notes

### Dependencies
- **Backend**: FastAPI, LangGraph (v0.2.74), LangChain-OpenAI, WebSockets
- **Frontend**: Next.js 15.1.0, React 19.0.0, TypeScript, Tailwind CSS
- **Package Manager**: Backend uses `uv`, frontend uses `npm`

### Security Features
- File type restrictions and size limits
- Session workspace isolation  
- Path traversal prevention
- CORS configured for localhost:3000

### Connection Patterns
The application supports both SSE (Server-Sent Events) for HTTP-based streaming and WebSockets for bidirectional communication. Frontend defaults to SSE but can switch to WebSocket if needed.

### Tool Execution
Agent tools execute in isolated session workspaces with virtual environments. Each session maintains its own file system context and command execution environment.