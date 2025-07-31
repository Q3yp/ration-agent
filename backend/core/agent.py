import os
import asyncio
from typing import Annotated, Optional
from langchain_openai import ChatOpenAI
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

import logging

# Fix for Windows async event loop
if os.name == 'nt':  # Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrchestratorState(AgentState):
    """Extended state for orchestrator-worker system"""
    # Task delegation variables
    current_task: str = ""
    task_context: dict = {}
    assigned_worker: str = ""
    
    # Worker findings (accumulate results)
    search_findings: Annotated[list, lambda x, y: x + y] = []
    code_results: Annotated[list, lambda x, y: x + y] = []
    
    # Artifacts (accumulate results)
    artifacts: Annotated[list, lambda x, y: x + y] = []
    
    # Workflow control
    workflow_stage: str = "analyzing"  # analyzing -> delegating -> working -> synthesizing


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
    """Create a new agent for a session with its own checkpointer instance"""
    
    # Get shared pool and create individual checkpointer for this session
    pool = await _connection_manager.get_shared_pool()
    checkpointer = AsyncPostgresSaver(pool)
    
    # Import node functions from nodes module
    from agents.nodes import supervisor_node, search_worker_node, code_worker_node
    
    # Build the orchestrator graph
    builder = StateGraph(OrchestratorState)
    
    # Add nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("search_worker", search_worker_node)
    builder.add_node("code_worker", code_worker_node)
    
    # Add edges
    builder.add_edge(START, "supervisor")
    builder.add_edge("search_worker", "supervisor")
    builder.add_edge("code_worker", "supervisor")
    
    # Compile with shared checkpointer
    agent = builder.compile(checkpointer=checkpointer)
    
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