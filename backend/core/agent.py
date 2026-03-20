import os
import asyncio
from typing import Annotated, Optional, Dict, Any
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
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

def replace_list(x: list, y: list) -> list:
    """Reducer function to replace list values"""
    return y

# Fix for Windows async event loop
if os.name == 'nt':  # Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FormulationState(AgentState):
    """Agent state for single-agent formulation system"""
    # Task context
    task_context: dict = {}
    
    # Artifacts (accumulate results)
    artifacts: Annotated[list, add_messages] = []
    
    # Feed formulation state (core business logic)
    current_formulation: Annotated[dict, replace_dict] = {}  # Last formulation result
    formulation_constraints: Annotated[list, replace_list] = []  # Nutritional constraints used in optimization
    feed_constraints: Annotated[dict, replace_dict] = {}  # Feed inclusion constraints
    
    # Feedbase references for export tool (store coordination)
    current_feedbase_name: Annotated[str, replace_string] = ""  # Current feedbase used
    current_user_id: Annotated[str, replace_string] = ""  # User ID for store access
    
    # Animal parameters for NASEM predictions (dairy cow)
    animal_params: Annotated[dict, replace_dict] = {}  # body_weight, milk_prod, dim, parity, bcs, etc.

class SharedConnectionManager:
    """Manages a single shared connection pool for all agent operations"""
    
    def __init__(self):
        self._shared_pool: Optional[AsyncConnectionPool] = None
        self._shared_store: Optional[AsyncPostgresStore] = None
    
    async def get_shared_pool(self) -> AsyncConnectionPool:
        """Get or create the shared connection pool"""
        if self._shared_pool is None:
            db_uri = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
            
            min_size = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
            max_size = int(os.getenv("DB_POOL_MAX_SIZE", "100"))
            if max_size < min_size:
                max_size = min_size

            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": None,
            }
            
            # Create shared pool for all sessions
            self._shared_pool = AsyncConnectionPool(
                db_uri,
                kwargs=connection_kwargs,
                min_size=min_size,
                max_size=max_size,
                timeout=10.0,
                open=False  # Prevent automatic opening in constructor
            )
            
            # Open the pool
            await self._shared_pool.open()
            logger.info("Initialized shared database connection pool")
        
        return self._shared_pool
    
    async def get_shared_store(self) -> AsyncPostgresStore:
        """Get or create the shared PostgresStore"""
        if self._shared_store is None:
            # Ensure we have a connection pool first
            pool = await self.get_shared_pool()
            
            # Create shared store using the same pool (assumes tables already exist)
            self._shared_store = AsyncPostgresStore(pool)
            logger.info("Created shared PostgreSQL store connection")
        
        return self._shared_store
    
    async def cleanup(self):
        """Clean up shared resources"""
        if self._shared_store:
            await self._shared_store.close()
            self._shared_store = None
            logger.info("Cleaned up shared store")
            
        if self._shared_pool:
            await self._shared_pool.close()
            self._shared_pool = None
            logger.info("Cleaned up shared connection pool")


# Global shared connection manager
_connection_manager = SharedConnectionManager()


class AgentRegistry:
    """Registry of reusable agents per animal type, with lite and full variants.
    
    Cache keys: "{animal_type}_lite" and "{animal_type}_full"
    """

    def __init__(self):
        self._agents: Dict[str, Any] = {}  # {cache_key: compiled_graph}
        self._lock = asyncio.Lock()

    async def initialize_all_agents(self):
        """Initialize lite agents for all 4 animal types at startup"""
        logger.info("Initializing all agent types (lite)...")
        for animal_type in ["dairy_cow", "beef_cow", "cat", "dog"]:
            await self.get_or_create_agent(animal_type, has_files=False)
        logger.info(f"✓ Initialized {len(self._agents)} agent variants")

    async def get_or_create_agent(self, animal_type: str, has_files: bool = False):
        """Get cached agent or create new one for the animal type + variant.
        
        Args:
            animal_type: Animal type (dairy_cow, beef_cow, cat, dog)
            has_files: Whether user has uploaded files (selects full vs lite)
        """
        variant = "full" if has_files else "lite"
        cache_key = f"{animal_type}_{variant}"

        if cache_key not in self._agents:
            async with self._lock:
                # Double-check after acquiring lock
                if cache_key not in self._agents:
                    logger.info(f"Creating {variant} agent for animal_type: {animal_type}")

                    # Get shared pool and store
                    pool = await _connection_manager.get_shared_pool()
                    store = await _connection_manager.get_shared_store()
                    checkpointer = AsyncPostgresSaver(pool)

                    from agents.nodes import create_agent

                    self._agents[cache_key] = await create_agent(
                        animal_type,
                        include_file_tools=has_files,
                        checkpointer=checkpointer,
                        store=store,
                    )
                    logger.info(f"✓ Agent created: {cache_key}")

        return self._agents[cache_key]


# Global agent registry
agent_registry = AgentRegistry()


async def cleanup_agent_session(session_id: str):
    """Clean up agent resources for a session (no-op with agent registry pattern)"""
    # With agent registry, agents are reused across sessions
    # Session state is managed by LangGraph using session_id as thread_id
    logger.debug(f"Agent cleanup for session {session_id} - using agent registry, no action needed")
    pass


async def cleanup_shared_resources():
    """Clean up shared agent resources on shutdown"""
    await _connection_manager.cleanup()
