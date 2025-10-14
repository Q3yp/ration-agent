import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set, List, Any
from dataclasses import dataclass, field
from psycopg_pool import AsyncConnectionPool
from core.agent import cleanup_agent_session
from utils.message_parser import UnifiedMessageParser
import tiktoken

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize tiktoken encoder for token counting - MUST succeed
TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
logger.info("Tiktoken encoder initialized successfully in session manager")


def check_token_limit(text: str, max_tokens: int = 7000) -> tuple[bool, int, str]:
    """
    Universal token limit checker that can be used by any tool.
    
    Args:
        text: The text to check token count for
        max_tokens: Maximum allowed tokens (default: 7000)
    
    Returns:
        tuple: (is_within_limit, token_count, error_message_if_exceeded)
    """
    token_count = len(TIKTOKEN_ENCODER.encode(text))
    logger.info(f"Token count: {token_count}")
    
    if token_count > max_tokens:
        error_msg = f"Result exceeded token limit of {max_tokens} tokens (got {token_count} tokens). Please refine your query to return less data."
        logger.warning(f"Exceeded token limit: {token_count} tokens")
        return False, token_count, error_msg
    
    return True, token_count, ""


def create_session_file_workspace(session_id: str, base_dir: str = None) -> str:
    """Create and return the file workspace directory for a session.
    
    Args:
        session_id: Unique session identifier
        base_dir: Base directory for workspaces (defaults to "files")
        
    Returns:
        Absolute path to the session workspace directory
    """
    if base_dir is None:
        base_dir = "files"
    
    base_path = Path(base_dir)
    session_dir = base_path / session_id
    
    # Create directories if they don't exist
    session_dir.mkdir(parents=True, exist_ok=True)
    
    return str(session_dir.absolute())


@dataclass
class SessionContext:
    """Full session context from database"""
    session_id: str
    workspace_path: str
    user_id: str = "default_user"
    animal_type: str = "dairy_cow"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_ready: bool = False
    active_connections: int = 0
    active: bool = True
    deleted: bool = False
    title: str = "新对话"
    title_generated: bool = False
    
    def resolve_file_path(self, filepath: str) -> str:
        """Resolve a relative or absolute file path within the session workspace."""
        if os.path.isabs(filepath):
            workspace_abs = os.path.abspath(self.workspace_path)
            filepath_abs = os.path.abspath(filepath)
            if filepath_abs.startswith(workspace_abs):
                return filepath_abs
            else:
                filename = os.path.basename(filepath)
                return os.path.join(workspace_abs, filename)
        else:
            return os.path.abspath(os.path.join(self.workspace_path, filepath))
    
    def get_workspace(self) -> Path:
        """Get workspace as Path object"""
        return Path(self.workspace_path)
    
    def ensure_workspace_exists(self) -> None:
        """Ensure the workspace directory exists"""
        self.get_workspace().mkdir(parents=True, exist_ok=True)

@dataclass 
class SessionInfo:
    """Lightweight session info for in-memory cache"""
    session_id: str
    title: str
    created_at: datetime
    last_accessed: datetime
    active_connections: int = 0

class SessionManager:
    """Centralized session lifecycle management with database persistence"""
    
    def __init__(self):
        self._session_info: Dict[str, SessionInfo] = {}  # Lightweight cache for display
        self._db_pool: Optional[AsyncConnectionPool] = None
        self._session_parsers: Dict[str, UnifiedMessageParser] = {}  # Cache parsers per session
        self._sessions: Dict[str, SessionContext] = {}  # In-memory session cache
        self._active_sessions: Set[str] = set()  # Set of active session IDs
    
    async def initialize(self):
        """Initialize database connection - no session loading"""
        # Use the shared connection pool for all database operations
        from core.agent import _connection_manager
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # Get the shared psycopg pool (compatible with both session management and LangGraph)
        self._db_pool = await _connection_manager.get_shared_pool()

        # Create a temporary checkpointer to initialize tables
        temp_checkpointer = AsyncPostgresSaver(self._db_pool)
        await temp_checkpointer.setup()

        # Create user_sessions table if it doesn't exist
        await self.create_user_sessions_table()

        # No session loading - everything is database-backed

    async def create_user_sessions_table(self):
        """Ensure user_sessions table exists (should be created by init.sql in Docker)"""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    # Check if table exists
                    await cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'user_sessions'
                        )
                    """)
                    table_exists = (await cur.fetchone())[0]

                    if not table_exists:
                        # Create the user_sessions table (fallback for non-Docker setups)
                        await cur.execute("""
                            CREATE TABLE user_sessions (
                                session_id VARCHAR(255) PRIMARY KEY,
                                user_id VARCHAR(255) NOT NULL DEFAULT 'default_user',
                                workspace_path TEXT NOT NULL,
                                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                last_accessed TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                                active BOOLEAN NOT NULL DEFAULT TRUE,
                                deleted BOOLEAN NOT NULL DEFAULT FALSE,
                                metadata JSONB DEFAULT '{}'::jsonb
                            )
                        """)

                        # Create indexes for better performance
                        await cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)
                        """)
                        await cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_user_sessions_active_deleted ON user_sessions(active, deleted)
                        """)
                        await cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_user_sessions_last_accessed ON user_sessions(last_accessed)
                        """)

                        logger.info("Created user_sessions table with indexes (fallback)")
                    else:
                        logger.debug("user_sessions table already exists")

        except Exception as e:
            logger.error(f"Failed to ensure user_sessions table exists: {e}")
            raise

    async def load_sessions_from_database(self):
        """Load all active, non-deleted sessions from database into memory cache"""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT session_id, user_id, workspace_path, created_at, last_accessed, active, deleted, metadata "
                        "FROM user_sessions WHERE active = TRUE AND deleted = FALSE"
                    )
                    rows = await cur.fetchall()
                    columns = [desc[0] for desc in cur.description]

                for row_data in rows:
                    row = dict(zip(columns, row_data))
                    # Get metadata - it's already a dict
                    metadata = row.get('metadata', {})

                    session_context = SessionContext(
                        session_id=row['session_id'],
                        user_id=row['user_id'],
                        workspace_path=row['workspace_path'],
                        animal_type=metadata.get('animal_type', 'dairy_cow'),
                        created_at=row['created_at'],
                        last_accessed=row['last_accessed'],
                        active=row['active'],
                        deleted=row.get('deleted', False),
                        title=metadata.get('title', '新对话'),
                        title_generated=metadata.get('title_generated', False)
                    )

                    self._sessions[row['session_id']] = session_context
                    self._active_sessions.add(row['session_id'])


        except Exception as e:
            logger.error(f"Failed to load sessions from database: {e}")
    
    async def persist_session_to_database(self, session_context: SessionContext):
        """Save session to database"""
        if not self._db_pool:
            return

        try:
            from psycopg.types.json import Jsonb

            existing_metadata = await self._get_session_metadata(session_context.session_id) or {}
            metadata_dict = dict(existing_metadata) if isinstance(existing_metadata, dict) else {}

            metadata_dict.update({
                'title': session_context.title,
                'title_generated': session_context.title_generated,
                'animal_type': session_context.animal_type,
            })

            if 'token_stats' not in metadata_dict or not isinstance(metadata_dict['token_stats'], dict):
                metadata_dict['token_stats'] = {
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0
                }

            metadata = Jsonb(metadata_dict)

            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO user_sessions (session_id, user_id, workspace_path, created_at, last_accessed, active, deleted, metadata) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (session_id) DO UPDATE SET "
                        "last_accessed = EXCLUDED.last_accessed, active = EXCLUDED.active, deleted = EXCLUDED.deleted, metadata = EXCLUDED.metadata",
                        (
                            session_context.session_id,
                            session_context.user_id,
                            session_context.workspace_path,
                            session_context.created_at,
                            session_context.last_accessed,
                            session_context.active,
                            session_context.deleted,
                            metadata
                        )
                )

        except Exception as e:
            logger.error(f"Failed to persist session {session_context.session_id}: {e}")
    
    async def _get_session_metadata(self, session_id: str) -> Optional[dict]:
        """Fetch existing session metadata without mutating state."""
        if not self._db_pool:
            return None

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT metadata FROM user_sessions WHERE session_id = %s",
                        (session_id,)
                    )
                    row = await cur.fetchone()
                    if not row:
                        return None
                    metadata = row[0]
                    if isinstance(metadata, dict):
                        return metadata
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch metadata for session {session_id}: {e}")
            return None
    
    async def update_session_last_accessed(self, session_id: str):
        """Update session last accessed time in database"""
        if not self._db_pool:
            return
        
        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE user_sessions SET last_accessed = NOW() WHERE session_id = %s",
                        (session_id,)
                    )
        except Exception as e:
            logger.error(f"Failed to update last_accessed for session {session_id}: {e}")
    
    async def deactivate_session(self, session_id: str):
        """Mark session as inactive in database"""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE user_sessions SET active = FALSE WHERE session_id = %s",
                        (session_id,)
                    )
        except Exception as e:
            logger.error(f"Failed to deactivate session {session_id}: {e}")

    async def mark_session_deleted(self, session_id: str):
        """Mark session as deleted in database (soft delete)"""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE user_sessions SET deleted = TRUE WHERE session_id = %s",
                        (session_id,)
                    )
        except Exception as e:
            logger.error(f"Failed to mark session {session_id} as deleted: {e}")
    
    async def get_all_active_sessions_from_db(self) -> List[Dict]:
        """Get all active, non-deleted sessions from database with stats"""
        if not self._db_pool:
            return []

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT session_id, user_id, workspace_path, created_at, last_accessed, metadata "
                        "FROM user_sessions WHERE active = TRUE AND deleted = FALSE ORDER BY last_accessed DESC"
                    )
                    rows = await cur.fetchall()
                    columns = [desc[0] for desc in cur.description]
                
                sessions = []
                for row_data in rows:
                    row = dict(zip(columns, row_data))
                    # Get metadata - it's already a dict
                    metadata = row.get('metadata', {})
                    
                    # Get session from memory if available for active connection count
                    session_context = self._sessions.get(row['session_id'])
                    active_connections = session_context.active_connections if session_context else 0
                    
                    sessions.append({
                        "exists": True,
                        "session_id": row['session_id'],
                        "user_id": row['user_id'],
                        "workspace_path": row['workspace_path'],
                        "created_at": row['created_at'].isoformat(),
                        "last_accessed": row['last_accessed'].isoformat(),
                        "active_connections": active_connections,
                        "agent_ready": True,
                        "title": metadata.get('title', '新对话')
                    })
                
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to get active sessions from database: {e}")
            return []

    async def create_session(self, session_id: str, user_id: str = "default_user", animal_type: str = "dairy_cow") -> SessionContext:
        """Create a new session with workspace and prepare agent context"""
        # Check if session already exists in database
        existing_session = await self.get_session_from_db(session_id)
        if existing_session:
            logger.debug(f"Session {session_id} already exists, returning existing session")
            return existing_session

        # Create workspace for session
        workspace_path = create_session_file_workspace(session_id)
        logger.info(f"Created workspace for session {session_id}: {workspace_path}")

        # Create session context
        session_context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            workspace_path=workspace_path,
            animal_type=animal_type
        )
        
        # Persist to database only
        await self.persist_session_to_database(session_context)
        
        return session_context
    
    async def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get existing session from database and update last_accessed"""
        session = await self.get_session_from_db(session_id)
        if session:
            # Update last accessed time
            await self.update_session_last_accessed(session_id)
        return session
    
    async def get_session_from_db(self, session_id: str) -> Optional[SessionContext]:
        """Get session directly from database - always fresh data"""
        if not self._db_pool:
            return None
        
        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT session_id, user_id, workspace_path, created_at, last_accessed, active, deleted, metadata "
                        "FROM user_sessions WHERE session_id = %s AND active = TRUE AND deleted = FALSE",
                        (session_id,)
                    )
                    row_data = await cur.fetchone()
                    if not row_data:
                        return None
                    
                    columns = [desc[0] for desc in cur.description]
                    row = dict(zip(columns, row_data))
                    metadata = row.get('metadata', {})
                    
                    return SessionContext(
                        session_id=row['session_id'],
                        user_id=row['user_id'],
                        workspace_path=row['workspace_path'],
                        animal_type=metadata.get('animal_type', 'dairy_cow'),
                        created_at=row['created_at'],
                        last_accessed=row['last_accessed'],
                        active=row['active'],
                        deleted=row.get('deleted', False),
                        title=metadata.get('title', '新对话'),
                        title_generated=metadata.get('title_generated', False)
                    )
        except Exception as e:
            logger.error(f"Failed to get session {session_id} from database: {e}")
            return None
    
    async def get_agent_for_session(self, session_id: str):
        """Get reusable agent based on session's animal type"""
        session = await self.get_session_from_db(session_id)
        if not session:
            raise RuntimeError(f"Session '{session_id}' not found")

        # Import here to avoid circular import
        from core.agent import agent_registry

        # Get agent for this animal type (creates on first access, reuses thereafter)
        return await agent_registry.get_or_create_agent(session.animal_type)
    
    def get_session_parser(self, session_id: str) -> UnifiedMessageParser:
        """Get or create message parser for session - thread-safe"""
        if session_id not in self._session_parsers:
            logger.debug(f"Creating new message parser for session {session_id}")
            self._session_parsers[session_id] = UnifiedMessageParser(session_id)
        
        return self._session_parsers[session_id]
    
    async def increment_connection(self, session_id: str):
        """Increment active connection count for session"""
        session = await self.get_session(session_id)
        if session:
            session.active_connections += 1
    
    async def decrement_connection(self, session_id: str):
        """Decrement active connection count for session"""
        session = await self.get_session(session_id)
        if session:
            session.active_connections = max(0, session.active_connections - 1)
    
    async def update_session_title(self, session_id: str, title: str):
        """Update session title both in memory and database"""
        session = await self.get_session(session_id)
        if session:
            session.title = title
            # Persist to database
            await self.persist_session_to_database(session)
    
    async def mark_title_generated(self, session_id: str):
        """Mark title as generated and persist to database immediately"""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    # Update metadata to mark title as generated
                    await cur.execute("""
                        UPDATE user_sessions
                        SET metadata = jsonb_set(
                            COALESCE(metadata, '{}'::jsonb),
                            '{title_generated}',
                            'true'::jsonb
                        )
                        WHERE session_id = %s AND deleted = FALSE
                    """, (session_id,))
                    logger.info(f"Marked title as generated for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to mark title as generated for session {session_id}: {e}")

    async def update_token_usage(self, session_id: str, prompt_tokens: int, completion_tokens: int, total_tokens: int):
        """
        Atomically increment cumulative token usage for a session in database metadata.
        Uses PostgreSQL JSONB operators for atomic increment - no SELECT needed, no race conditions.
        """
        if not self._db_pool:
            return

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    # Persist absolute token counts provided by the latest run.
                    await cur.execute("""
                        UPDATE user_sessions
                        SET metadata = jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    COALESCE(metadata, '{}'::jsonb),
                                    '{token_stats,prompt_tokens}',
                                    to_jsonb(%s)
                                ),
                                '{token_stats,completion_tokens}',
                                to_jsonb(COALESCE((metadata->'token_stats'->>'completion_tokens')::int, 0) + %s)
                            ),
                            '{token_stats,total_tokens}',
                            to_jsonb(COALESCE((metadata->'token_stats'->>'total_tokens')::int, 0) + %s)
                        )
                        WHERE session_id = %s AND deleted = FALSE
                    """, (prompt_tokens, completion_tokens, total_tokens, session_id))

                    logger.debug(
                        "Persisted token usage for session %s: prompt=%s (absolute), +%s completion, +%s total",
                        session_id,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                    )
        except Exception as e:
            logger.error(f"Failed to update token usage for session {session_id}: {e}")
    

    async def get_session_stats(self, session_id: str) -> Dict:
        """Get session statistics and metadata"""
        session = await self.get_session_from_db(session_id)
        if not session:
            return {"exists": False}

        # Get token stats from metadata
        token_stats = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

        if not self._db_pool:
            return {"exists": False}

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT metadata->'token_stats' as token_stats
                        FROM user_sessions
                        WHERE session_id = %s AND deleted = FALSE
                    """, (session_id,))
                    result = await cur.fetchone()

                    if result and result[0]:
                        token_stats = result[0]
        except Exception as e:
            logger.error(f"Failed to get token stats for session {session_id}: {e}")

        return {
            "exists": True,
            "session_id": session.session_id,
            "user_id": session.user_id,
            "workspace_path": session.workspace_path,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "active_connections": session.active_connections,
            "agent_ready": True,  # Agents are created on-demand
            "title": session.title,
            "token_usage": token_stats
        }

    async def get_session_workspace_path(self, session_id: str) -> Path:
        """Get the workspace Path object for a session. 
        
        This is a shared utility for tools that need to create files in the session workspace.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Path object for the session workspace
            
        Raises:
            RuntimeError: If session is not found
        """
        session = await self.get_session(session_id)
        if not session:
            raise RuntimeError(f"Session '{session_id}' not found")
        
        session.ensure_workspace_exists()
        return session.get_workspace()
    
    async def list_active_sessions(self) -> list:
        """Get list of all active session IDs with their stats from database"""
        return await self.get_all_active_sessions_from_db()
    
    async def cleanup_session(self, session_id: str, remove_files: bool = False):
        """Clean up session resources"""
        # Get session from database to ensure it exists
        session = await self.get_session_from_db(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found in database for cleanup")
            return

        # Clean up agent connection pools first
        try:
            await cleanup_agent_session(session_id)
        except Exception as e:
            logger.error(f"Error cleaning up agent resources for session {session_id}: {e}")

        if remove_files:
            workspace_path = Path(session.workspace_path)
            if workspace_path.exists():
                import shutil
                shutil.rmtree(workspace_path)

        # Deactivate in database
        await self.deactivate_session(session_id)

        # Clean up cached parser
        if session_id in self._session_parsers:
            del self._session_parsers[session_id]
            logger.debug(f"Cleaned up cached parser for session {session_id}")

        # Remove from memory cache if present
        if session_id in self._sessions:
            del self._sessions[session_id]
        self._active_sessions.discard(session_id)

    async def soft_delete_session(self, session_id: str):
        """Soft delete a session - mark as deleted but preserve data and history"""
        # Check if session exists in database first
        session = await self.get_session_from_db(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found in database for soft delete")
            return

        # Clean up agent connection pools but keep session data
        try:
            await cleanup_agent_session(session_id)
        except Exception as e:
            logger.error(f"Error cleaning up agent resources for session {session_id}: {e}")

        # Mark as deleted in database (soft delete)
        await self.mark_session_deleted(session_id)

        # Clean up cached parser
        if session_id in self._session_parsers:
            del self._session_parsers[session_id]
            logger.debug(f"Cleaned up cached parser for session {session_id}")

        # Remove from memory cache if present
        if session_id in self._sessions:
            del self._sessions[session_id]
        self._active_sessions.discard(session_id)

    async def soft_delete_all_sessions(self):
        """Soft delete all active sessions - mark as deleted but preserve data and history"""
        # Get all active sessions from database instead of memory
        active_sessions = await self.get_all_active_sessions_from_db()
        session_ids = [session["session_id"] for session in active_sessions]
        deleted_count = 0
        
        for session_id in session_ids:
            try:
                await self.soft_delete_session(session_id)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error soft deleting session {session_id}: {e}")
                continue
        
        return {
            "total_processed": len(session_ids),
            "deleted_count": deleted_count,
            "failed_count": len(session_ids) - deleted_count
        }

    async def list_user_sessions(self, user_id: str) -> list:
        """Get list of active session IDs for a specific user"""
        if not self._db_pool:
            logger.warning("Database pool not initialized")
            return []

        try:
            async with self._db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT session_id, user_id, workspace_path, created_at, last_accessed, active, deleted, metadata
                        FROM user_sessions
                        WHERE user_id = %s AND active = TRUE AND deleted = FALSE
                        ORDER BY last_accessed DESC
                        """, 
                        (user_id,)
                    )
                    rows = await cur.fetchall()
                    columns = [desc[0] for desc in cur.description]

                    sessions = []
                    for row_data in rows:
                        row = dict(zip(columns, row_data))
                        metadata = row.get('metadata', {})

                        # Extract token stats from metadata
                        token_stats = metadata.get('token_stats', {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        })

                        sessions.append({
                            "session_id": row['session_id'],
                            "user_id": row['user_id'],
                            "title": metadata.get('title', '新对话'),
                            "animal_type": metadata.get('animal_type', 'dairy_cow'),
                            "created_at": row['created_at'].isoformat(),
                            "last_accessed": row['last_accessed'].isoformat(),
                            "active": row['active'],
                            "workspace_path": row['workspace_path'],
                            "token_usage": token_stats
                        })

                    return sessions

        except Exception as e:
            logger.error(f"Failed to list user sessions for {user_id}: {e}")
            return []

    async def soft_delete_user_sessions(self, user_id: str) -> dict:
        """Soft delete all sessions for a specific user"""
        if not self._db_pool:
            logger.warning("Database pool not initialized")
            return {"total_processed": 0, "deleted_count": 0, "failed_count": 0}

        # Get all sessions for the user
        user_sessions = await self.list_user_sessions(user_id)
        session_ids = [session["session_id"] for session in user_sessions]

        if not session_ids:
            return {"total_processed": 0, "deleted_count": 0, "failed_count": 0}

        deleted_count = 0
        for session_id in session_ids:
            try:
                await self.soft_delete_session(session_id)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error soft deleting session {session_id} for user {user_id}: {e}")
                continue
        
        return {
            "total_processed": len(session_ids),
            "deleted_count": deleted_count,
            "failed_count": len(session_ids) - deleted_count
        }


# Global session manager instance
session_manager = SessionManager()
