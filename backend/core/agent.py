import os
import asyncio
from typing import Annotated, Optional
from langchain_openai import ChatOpenAI
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

import logging

# Reducer functions for state annotations (must be named functions for serialization)
def add_messages(x: list, y: list) -> list:
    """Reducer function to concatenate message lists"""
    return x + y

def merge_dicts(x: dict, y: dict) -> dict:
    """Reducer function to merge dictionaries"""
    return {**x, **y}

def replace_dict(x: dict, y: dict) -> dict:
    """Reducer function to replace dictionary"""
    return y

def add_int(x: int, y: int) -> int:
    """Reducer function to add integers"""
    return x + y

def replace_string(x: str, y: str) -> str:
    """Reducer function to replace string values"""
    return y

# Fix for Windows async event loop
if os.name == 'nt':  # Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FormulationState(AgentState):
    """Simplified state for LangGraph Multi-Agent Supervisor system"""
    # Task context
    task_context: dict = {}
    
    # Artifacts (accumulate results) - using named functions for serialization
    artifacts: Annotated[list, add_messages] = []
    
    # Feed formulation state (core business logic)
    feed_database: Annotated[dict, merge_dicts] = {}  # Feed name -> feed data
    current_formulation: Annotated[dict, replace_dict] = {}  # Last formulation result
    
    # Active agent tracking (for supervisor framework)
    active_agent: Annotated[str, replace_string] = "nutritionist"

class WorkerState(AgentState):
    """Extended state for formulation system with isolated message threads"""
    # Task context
    task_context: dict = {}
    
    # Artifacts (accumulate results) - using named functions for serialization
    artifacts: Annotated[list, add_messages] = []

    # Message count tracker (total messages processed so far)
    processed_message_count: Annotated[int, add_int] = 0
    
    # Feed formulation state
    feed_database: Annotated[dict, merge_dicts] = {}  # Feed name -> feed data
    current_formulation: Annotated[dict, replace_dict] = {}  # Last formulation result


class SharedConnectionManager:
    """Manages a single shared connection pool for all agent operations"""
    
    def __init__(self):
        self._shared_pool: Optional[AsyncConnectionPool] = None
    
    async def get_shared_pool(self) -> AsyncConnectionPool:
        """Get or create the shared connection pool"""
        if self._shared_pool is None:
            db_uri = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
            
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": None,
            }
            
            # Create shared pool for all sessions
            self._shared_pool = AsyncConnectionPool(
                db_uri,
                kwargs=connection_kwargs,
                min_size=5,
                max_size=20,  # Increased for shared usage
                timeout=10.0,
                open=False  # Prevent automatic opening in constructor
            )
            
            # Open the pool
            await self._shared_pool.open()
            logger.info("Initialized shared database connection pool")
        
        return self._shared_pool
    
    async def cleanup(self):
        """Clean up shared resources"""
        if self._shared_pool:
            await self._shared_pool.close()
            self._shared_pool = None
            logger.info("Cleaned up shared connection pool")


# Global shared connection manager
_connection_manager = SharedConnectionManager()


async def create_agent_for_session(session_id: str):
    """Create a new agent for a session using LangGraph Multi-Agent Supervisor pattern"""
    
    # Get shared pool and create individual checkpointer for this session
    pool = await _connection_manager.get_shared_pool()
    checkpointer = AsyncPostgresSaver(pool)
    
    # Import supervisor creation function from nodes module
    from agents.nodes import create_nutritionist_supervisor
    
    # Create the supervisor workflow
    supervisor_workflow = await create_nutritionist_supervisor(session_id)
    
    # Compile with shared checkpointer
    # Note: recursion_limit is set during invoke/stream, not compile
    agent = supervisor_workflow.compile(checkpointer=checkpointer)
    
    return agent


async def cleanup_agent_session(session_id: str):
    """Clean up agent resources for a session (no per-session cleanup needed with shared pool)"""
    # With shared connection pool, no per-session cleanup needed
    # Session state is managed by LangGraph using session_id as thread_id
    logger.debug(f"Agent cleanup for session {session_id} - using shared pool, no action needed")
    pass


async def cleanup_shared_resources():
    """Clean up shared agent resources on shutdown"""
    await _connection_manager.cleanup()