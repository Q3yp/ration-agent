from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import tiktoken

from api.routes import router
from services.session_manager import session_manager
from core.agent import cleanup_shared_resources

load_dotenv()

# Initialize tiktoken encoder at app startup
TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    
    # Initialize SessionManager with database connection
    try:
        await session_manager.initialize()
    except Exception as e:
        raise
    
    yield
    
    # Clean up shared resources
    try:
        await cleanup_shared_resources()
    except Exception as e:
        pass  # Log error if needed, but don't prevent shutdown

app = FastAPI(
    title="LangGraph ReAct Agent API",
    description="A FastAPI backend with LangGraph ReAct agent for chat interactions",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

def start():
    """Entry point for uv run start command"""
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    start()