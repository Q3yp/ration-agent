import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set, List
from dataclasses import dataclass, field
from psycopg_pool import AsyncConnectionPool
from core.agent import create_agent_for_session, cleanup_agent_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_session_file_workspace(session_id: str) -> str:
    """Create and return the file workspace directory for a session."""
    base_dir = Path("files")
    session_dir = base_dir / session_id
    
    # Create directories if they don't exist
    session_dir.mkdir(parents=True, exist_ok=True)
    
    return str(session_dir.absolute())


@dataclass
class SessionContext:
    """Represents a session with its metadata and state"""
    session_id: str
    workspace_path: str
    user_id: str = "default_user"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_ready: bool = False
    active_connections: int = 0
    active: bool = True
    deleted: bool = False
    title: str = "New Conversation"
    title_generated: bool = False


class SessionManager:
    """Centralized session lifecycle management with database persistence"""
    
    def __init__(self):
        self._sessions: Dict[str, SessionContext] = {}
        self._active_sessions: Set[str] = set()
        self._db_pool: Optional[AsyncConnectionPool] = None
    
    async def initialize(self):
        """Initialize database connection and load existing sessions"""
        # Use the shared connection pool for all database operations
        from core.agent import _connection_manager
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        
        # Get the shared psycopg pool (compatible with both session management and LangGraph)
        self._db_pool = await _connection_manager.get_shared_pool()
        
        # Create a temporary checkpointer to initialize tables
        temp_checkpointer = AsyncPostgresSaver(self._db_pool)
        await temp_checkpointer.setup()
        
        # Load existing sessions from database
        await self.load_sessions_from_database()
    
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
                        created_at=row['created_at'],
                        last_accessed=row['last_accessed'],
                        active=row['active'],
                        deleted=row.get('deleted', False),
                        title=metadata.get('title', 'New Conversation'),
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
            # Create metadata with title and title_generated flag as JSONB
            metadata = Jsonb({
                'title': session_context.title,
                'title_generated': session_context.title_generated
            })

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
                        "title": metadata.get('title', 'New Conversation')
                    })
                
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to get active sessions from database: {e}")
            return []

    async def create_session(self, session_id: str, user_id: str = "default_user") -> SessionContext:
        """Create a new session with workspace and prepare agent context"""
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Create workspace for session
        workspace_path = create_session_file_workspace(session_id)
        
        # Create session context
        session_context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            workspace_path=workspace_path
        )
        
        # Register session in memory
        self._sessions[session_id] = session_context
        self._active_sessions.add(session_id)
        
        # Persist to database
        await self.persist_session_to_database(session_context)
        
        return session_context
    
    async def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get existing session or None if not found"""
        session = self._sessions.get(session_id)
        if session:
            session.last_accessed = datetime.now(timezone.utc)
            # Update database asynchronously
            await self.update_session_last_accessed(session_id)
        return session
    
    async def get_session_agent(self, session_id: str):
        """Get or create agent for session (session must exist)"""
        session = await self.get_session(session_id)
        if not session:
            raise RuntimeError(f"Session '{session_id}' not found")
        
        # Create agent for this session
        agent = await create_agent_for_session(session_id)
        return agent
    
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

    async def get_session_stats(self, session_id: str) -> Dict:
        """Get session statistics and metadata"""
        session = await self.get_session(session_id)
        if not session:
            return {"exists": False}
        
        return {
            "exists": True,
            "session_id": session.session_id,
            "user_id": session.user_id,
            "workspace_path": session.workspace_path,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "active_connections": session.active_connections,
            "agent_ready": True,  # Agents are created on-demand
            "title": session.title
        }
    
    async def list_active_sessions(self) -> list:
        """Get list of all active session IDs with their stats from database"""
        return await self.get_all_active_sessions_from_db()
    
    async def cleanup_session(self, session_id: str, remove_files: bool = False):
        """Clean up session resources"""
        if session_id in self._sessions:
            session = self._sessions[session_id]

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

            del self._sessions[session_id]
            self._active_sessions.discard(session_id)

    async def soft_delete_session(self, session_id: str):
        """Soft delete a session - mark as deleted but preserve data and history"""
        if session_id in self._sessions:
            session = self._sessions[session_id]

            # Clean up agent connection pools but keep session data
            try:
                await cleanup_agent_session(session_id)
            except Exception as e:
                logger.error(f"Error cleaning up agent resources for session {session_id}: {e}")

            # Mark as deleted in database (soft delete)
            await self.mark_session_deleted(session_id)

            # Remove from memory cache but don't delete from database
            del self._sessions[session_id]
            self._active_sessions.discard(session_id)


# Global session manager instance
session_manager = SessionManager()