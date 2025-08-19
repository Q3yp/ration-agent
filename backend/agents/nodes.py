import os
import logging
from typing import Annotated
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph_supervisor import create_supervisor, create_handoff_tool

from utils.prompt_loader import apply_prompt_template
from utils.tools import get_tools, get_search_tools, get_nutritionist_tools, get_coder_tools
from utils.model_config import get_model_config
from core.agent import FormulationState

# Configure logging
logger = logging.getLogger(__name__)


# Custom handoff tools with task descriptions
def create_nutritionist_handoff_tools():
    """Create custom handoff tools for nutritionist supervisor"""
    
    @tool("delegate_to_researcher")
    def delegate_to_researcher(
        task_description: Annotated[str, "Detailed research task for the researcher agent"],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Delegate research tasks to the researcher agent."""
        tool_message = ToolMessage(
            content=f"Task delegated to researcher: {task_description}",
            name="delegate_to_researcher",
            tool_call_id=tool_call_id,
        )
        messages = state["messages"]
        return Command(
            goto="researcher",
            graph=Command.PARENT,
            update={
                "messages": messages + [tool_message],
                "active_agent": "researcher",
                "task_context": {"current_task": task_description, "delegated_by": "nutritionist"}
            },
        )
    
    @tool("delegate_to_coder")
    def delegate_to_coder(
        task_description: Annotated[str, "Detailed coding/analysis task for the coder agent"],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Delegate coding and data analysis tasks to the coder agent."""
        tool_message = ToolMessage(
            content=f"Task delegated to coder: {task_description}",
            name="delegate_to_coder",
            tool_call_id=tool_call_id,
        )
        messages = state["messages"]
        return Command(
            goto="coder",
            graph=Command.PARENT,
            update={
                "messages": messages + [tool_message],
                "active_agent": "coder",
                "task_context": {"current_task": task_description, "delegated_by": "nutritionist"}
            },
        )
    
    return [delegate_to_researcher, delegate_to_coder]


def create_worker_handoff_tool(agent_name: str):
    """Create handoff tool for worker agents to return to supervisor"""
    
    @tool(f"return_to_nutritionist")
    def return_to_nutritionist(
        findings: Annotated[str, "Results and findings from completing the assigned task"],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Return completed task results to the nutritionist supervisor."""
        tool_message = ToolMessage(
            content=f"Task completed by {agent_name}. Results: {findings}",
            name="return_to_nutritionist",
            tool_call_id=tool_call_id,
        )
        messages = state["messages"]
        return Command(
            goto="nutritionist",
            graph=Command.PARENT,
            update={
                "messages": messages + [tool_message],
                "active_agent": "nutritionist",
                "task_context": {"completed_task": findings, "completed_by": agent_name}
            },
        )
    
    return return_to_nutritionist


async def create_researcher_agent(session_id: str):
    """Create specialized researcher agent"""
    model = get_model_config("researcher")
    search_tools = get_search_tools()
    handoff_tool = create_worker_handoff_tool("researcher")
    
    all_tools = search_tools + [handoff_tool]
    
    researcher = create_react_agent(
        model=model,
        tools=all_tools,
        state_schema=FormulationState,
        prompt=lambda state: apply_prompt_template("researcher", state),
        checkpointer=True,
    )
    
    researcher.name = "researcher"
    return researcher


async def create_coder_agent(session_id: str):
    """Create specialized coder agent"""
    model = get_model_config("coder")
    coder_tools = await get_coder_tools(session_id)
    handoff_tool = create_worker_handoff_tool("coder")
    
    all_tools = coder_tools + [handoff_tool]
    
    coder = create_react_agent(
        model=model,
        tools=all_tools,
        state_schema=FormulationState,
        prompt=lambda state: apply_prompt_template("coder", state),
        checkpointer=True,
    )
    
    coder.name = "coder"
    return coder


async def create_nutritionist_supervisor(session_id: str):
    """Create the nutritionist supervisor that manages researcher and coder agents"""
    
    # Create worker agents
    researcher_agent = await create_researcher_agent(session_id)
    coder_agent = await create_coder_agent(session_id)
    
    # Get nutritionist model and tools
    model = get_model_config("nutritionist")
    nutritionist_tools = await get_nutritionist_tools(session_id)
    
    # Create custom handoff tools
    handoff_tools = create_nutritionist_handoff_tools()
    
    # Combine all tools for the supervisor
    all_supervisor_tools = nutritionist_tools + handoff_tools
    
    # Create supervisor using langgraph-supervisor
    supervisor = create_supervisor(
        agents=[researcher_agent, coder_agent],
        model=model,
        state_schema=FormulationState, 
        prompt=lambda state: apply_prompt_template("nutritionist", state),
        tools=all_supervisor_tools,
        supervisor_name="nutritionist",
        output_mode="last_message",  
        add_handoff_messages=True,   # Include handoff messages in conversation
    )
    
    return supervisor


# Legacy node functions for backward compatibility (if needed)
async def nutritionist_node(state: FormulationState, config: RunnableConfig = None):
    """Legacy nutritionist node - replaced by supervisor pattern"""
    logger.warning("Using legacy nutritionist_node - consider updating to supervisor pattern")
    # This could be a fallback or migration helper
    pass


async def researcher_node(state: FormulationState, config: RunnableConfig = None):
    """Legacy researcher node - now handled by supervisor pattern"""
    logger.warning("Using legacy researcher_node - now handled by supervisor pattern")
    pass


async def coder_node(state: FormulationState, config: RunnableConfig = None):
    """Legacy coder node - now handled by supervisor pattern"""
    logger.warning("Using legacy coder_node - now handled by supervisor pattern")
    pass