import os
import subprocess
from pathlib import Path
from langchain_core.tools import tool
from langchain_community.agent_toolkits import FileManagementToolkit


async def bash_command(command: str, session_id: str) -> str:
    """Execute a bash command in the session workspace."""
    try:
        # Import here to avoid circular imports
        from session_manager import session_manager
        
        # Get session context
        session = await session_manager.get_session(session_id)
        if not session:
            return f"Error: Session '{session_id}' not found"
        
        session_workspace = session.workspace_path
        
        # Execute command with project venv activated
        project_root = Path(__file__).parent  # backend directory
        if os.name == 'nt':  # Windows
            full_command = f"{project_root}\\.venv\\Scripts\\activate && {command}"
        else:  # Unix/Linux/Mac
            full_command = f"source {project_root}/.venv/bin/activate && {command}"
        
        result = subprocess.run(
            full_command,
            shell=True,
            executable='/bin/bash',  # Force use of bash instead of sh
            cwd=session_workspace,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}"
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if not output:
            output = "Command executed successfully with no output."
        
        output += f"\nReturn code: {result.returncode}"
        return output
        
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def create_bash_command_tool(session_id: str):
    """Create a bash command tool bound to a specific session"""
    @tool
    async def bash_command_for_session(command: str) -> str:
        """Execute a bash command in the session workspace."""
        return await bash_command(command, session_id)
    
    return bash_command_for_session




async def get_file_management_tools(session_id: str):
    """Get file management tools for a specific session."""
    # Import here to avoid circular imports
    from session_manager import session_manager
    
    # Get session context
    session = await session_manager.get_session(session_id)
    if not session:
        raise RuntimeError(f"Session '{session_id}' not found")
    
    session_workspace = session.workspace_path
    
    # Create FileManagementToolkit with session-specific root directory
    file_toolkit = FileManagementToolkit(root_dir=session_workspace)
    
    return file_toolkit.get_tools()


async def get_tools(session_id: str):
    """Get all available tools for a session."""
    # Create session-bound bash tool
    session_bash_tool = create_bash_command_tool(session_id)
    
    # Get file management tools for the session
    file_tools = await get_file_management_tools(session_id)
    
    return [session_bash_tool] + file_tools