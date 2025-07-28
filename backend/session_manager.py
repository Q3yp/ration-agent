import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from tools import get_tools
from agent import create_agent_for_session

# Configure logging
logging.basicConfig(level=logging.DEBUG)
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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_ready: bool = False
    active_connections: int = 0


class SessionManager:
    """Centralized session lifecycle management"""
    
    def __init__(self):
        self._sessions: Dict[str, SessionContext] = {}
        self._active_sessions: Set[str] = set()
    
    def create_session(self, session_id: str) -> SessionContext:
        """Create a new session with workspace and prepare agent context"""
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Create workspace for session
        workspace_path = create_session_file_workspace(session_id)
        
        # Create session context
        session_context = SessionContext(
            session_id=session_id,
            workspace_path=workspace_path
        )
        
        # Register session
        self._sessions[session_id] = session_context
        self._active_sessions.add(session_id)
        
        return session_context
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get existing session or None if not found"""
        session = self._sessions.get(session_id)
        if session:
            session.last_accessed = datetime.now(timezone.utc)
        return session
    
    async def get_session_agent(self, session_id: str):
        """Get or create agent for session (session must exist)"""
        logger.info(f"Getting agent for session: {session_id}")
        
        session = self.get_session(session_id)
        if not session:
            logger.error(f"Session '{session_id}' not found")
            raise RuntimeError(f"Session '{session_id}' not found")
        
        logger.debug(f"Session found, creating agent for: {session_id}")
        # Create agent for this session
        agent = await create_agent_for_session(session_id)
        logger.info(f"Agent successfully created/retrieved for session: {session_id}")
        return agent
    
    def increment_connection(self, session_id: str):
        """Increment active connection count for session"""
        session = self.get_session(session_id)
        if session:
            session.active_connections += 1
    
    def decrement_connection(self, session_id: str):
        """Decrement active connection count for session"""
        session = self.get_session(session_id)
        if session:
            session.active_connections = max(0, session.active_connections - 1)
    
    def get_session_stats(self, session_id: str) -> Dict:
        """Get session statistics and metadata"""
        session = self.get_session(session_id)
        if not session:
            return {"exists": False}
        
        return {
            "exists": True,
            "session_id": session.session_id,
            "workspace_path": session.workspace_path,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "active_connections": session.active_connections,
            "agent_ready": True  # Agents are created on-demand
        }
    
    def list_active_sessions(self) -> list:
        """Get list of all active session IDs with their stats"""
        return [
            self.get_session_stats(session_id) 
            for session_id in self._active_sessions
        ]
    
    def cleanup_session(self, session_id: str, remove_files: bool = False):
        """Clean up session resources"""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            
            if remove_files:
                workspace_path = Path(session.workspace_path)
                if workspace_path.exists():
                    import shutil
                    shutil.rmtree(workspace_path)
            
            del self._sessions[session_id]
            self._active_sessions.discard(session_id)


# Global session manager instance
session_manager = SessionManager()