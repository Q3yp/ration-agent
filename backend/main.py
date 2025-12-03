from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import tiktoken

from api.routes import router
from auth.routes import auth_router
from auth.admin_routes import admin_router
from api.routes import router
from auth.routes import auth_router
from auth.admin_routes import admin_router
from api.feedback_routes import feedback_router
from migrations.schema_manager import SchemaManager
from services.session_manager import session_manager
from core.agent import cleanup_shared_resources

import logging

load_dotenv()

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress SQLAlchemy logs early
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)

class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return '/health' not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

# Initialize tiktoken encoder at app startup
TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    
    # Initialize database, update schema, and seed data
    try:
        schema_manager = SchemaManager()
        await schema_manager.update_schema()
        await schema_manager.seed_feedbases()
    except Exception as e:
        print(f"Failed to initialize database/schema: {e}")
        raise

    # Initialize SessionManager with database connection
    try:
        await session_manager.initialize()
    except Exception as e:
        raise

    # Initialize all agent types (eager loading for instant first response)
    try:
        from core.agent import agent_registry
        await agent_registry.initialize_all_agents()
        print("✓ Initialized 4 agent types (dairy_cow, beef_cow, cat, dog)")
    except Exception as e:
        print(f"Warning: Failed to initialize agents: {e}")
        print("Agents will be created on-demand when first accessed")
        # Non-fatal - agents will be created on-demand

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
app.include_router(feedback_router)

def start():
    """Entry point for uv run start command"""
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    start()
