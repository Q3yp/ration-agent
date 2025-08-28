from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import tiktoken

from api.routes import router
from auth.routes import auth_router
from auth.admin_routes import admin_router
from auth.database import create_db_and_tables
from services.session_manager import session_manager
from core.agent import cleanup_shared_resources

import logging

load_dotenv()

class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return '/health' not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

# Initialize tiktoken encoder at app startup
TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    
    # Initialize database and create tables
    try:
        await create_db_and_tables()
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise

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
    allow_origins=["http://localhost:3000", "http://47.104.108.233:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router, prefix="/auth")
app.include_router(admin_router)

def start():
    """Entry point for uv run start command"""
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    start()