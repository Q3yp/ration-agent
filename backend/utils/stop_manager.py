"""
StopManager: Pure asyncio task cancellation for agent interruption
"""
import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class StopManager:
    """Pure asyncio task cancellation manager - no database state tracking"""
    
    # Class-level registry of active tasks
    active_tasks: Dict[str, asyncio.Task] = {}
    
    @staticmethod
    async def register_task(session_id: str, task: asyncio.Task):
        """Register an active task for a session"""
        try:
            StopManager.active_tasks[session_id] = task
            logger.info(f"STOP_MANAGER: Registered task for session {session_id}")
        except Exception as e:
            logger.error(f"STOP_MANAGER: Failed to register task for session {session_id}: {e}")
    
    @staticmethod
    async def cancel_task(session_id: str) -> bool:
        """Cancel the active task for a session"""
        try:
            if session_id in StopManager.active_tasks:
                task = StopManager.active_tasks[session_id]
                if not task.cancelled() and not task.done():
                    task.cancel()
                    logger.info(f"STOP_MANAGER: Task cancelled for session {session_id}")
                    return True
                else:
                    logger.info(f"STOP_MANAGER: Task for session {session_id} already finished/cancelled")
                    return False
            else:
                logger.info(f"STOP_MANAGER: No active task found for session {session_id}")
                return False
        except Exception as e:
            logger.error(f"STOP_MANAGER: Failed to cancel task for session {session_id}: {e}")
            return False
    
    @staticmethod
    async def cleanup_task(session_id: str):
        """Remove task from registry when completed"""
        try:
            if session_id in StopManager.active_tasks:
                StopManager.active_tasks.pop(session_id)
                logger.info(f"STOP_MANAGER: Cleaned up task for session {session_id}")
        except Exception as e:
            logger.error(f"STOP_MANAGER: Failed to cleanup task for session {session_id}: {e}")
    
    @staticmethod
    async def is_task_active(session_id: str) -> bool:
        """Check if a task is currently active for a session"""
        try:
            if session_id in StopManager.active_tasks:
                task = StopManager.active_tasks[session_id]
                return not task.cancelled() and not task.done()
            return False
        except Exception as e:
            logger.error(f"STOP_MANAGER: Failed to check task status for session {session_id}: {e}")
            return False