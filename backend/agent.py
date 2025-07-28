import os
import asyncio
from typing import Annotated
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
logging.basicConfig(level=logging.DEBUG)
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
    
    # Workflow control
    workflow_stage: str = "analyzing"  # analyzing -> delegating -> working -> synthesizing


async def create_agent_for_session(session_id: str):
    """Create a new agent for a session with its own model and checkpointer"""
    
    # Create PostgreSQL connection pool and checkpointer
    db_uri = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": None,  # Key fix: set to None instead of 0
    }
    
    # Configure connection pool with smaller size and timeouts
    async with AsyncConnectionPool(
        db_uri, 
        kwargs=connection_kwargs,
        min_size=1,
        max_size=5,
        timeout=10.0
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        
        # Import node functions from nodes module
        from nodes import supervisor_node, search_worker_node, code_worker_node
        
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
        
        # Compile with checkpointer
        agent = builder.compile(checkpointer=checkpointer)
        
        return agent