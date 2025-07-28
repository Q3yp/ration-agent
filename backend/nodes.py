import os
import re
from typing import Literal
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from prompt_loader import apply_prompt_template
from tools import get_tools
from search_tools import get_search_tools
from agent import OrchestratorState


def supervisor_node(state: OrchestratorState, config: RunnableConfig = None) -> Command[Literal["search_worker", "code_worker", "__end__"]]:
    """Supervisor node that analyzes requests and routes to appropriate workers"""
    # Get model
    model = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL"),
        temperature=0,
        streaming=True,
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        stream_usage=False
    )
    
    # For now, supervisor has no working tools (will be added later)
    # It uses create_react_agent for consistency but focuses on analysis
    supervisor_tools = []  # TODO: Add actual supervisor tools when implemented
    
    supervisor = create_react_agent(
        model,
        supervisor_tools,
        prompt=lambda state: apply_prompt_template("supervisor", state)
    )
    
    # Invoke the supervisor agent
    result = supervisor.invoke(state)
    
    # Parse the final response to determine routing
    if result.get("messages"):
        last_message = result["messages"][-1]
        if hasattr(last_message, 'content'):
            routing_decision = _parse_supervisor_response(last_message.content)
            
            # Return Command based on routing decision
            if routing_decision["action"] == "SEARCH_WORKER":
                return Command(
                    update={
                        **result,
                        "current_task": routing_decision["task"],
                        "assigned_worker": "search_worker",
                        "workflow_stage": "working"
                    },
                    goto="search_worker"
                )
            elif routing_decision["action"] == "CODE_WORKER":
                return Command(
                    update={
                        **result,
                        "current_task": routing_decision["task"],
                        "assigned_worker": "code_worker",
                        "workflow_stage": "working"
                    },
                    goto="code_worker"
                )
    
    # Default: end the conversation with supervisor's response
    return Command(
        update={**result, "workflow_stage": "completed"},
        goto="__end__"
    )


def _parse_supervisor_response(response_content: str) -> dict:
    """Parse supervisor LLM response to extract routing decision"""
    # Extract routing decision using regex
    routing_pattern = r"\*\*ROUTING_DECISION:\*\*\s*(\w+)"
    task_pattern = r"\*\*TASK_DESCRIPTION:\*\*\s*(.+?)(?=\n\n|$)"
    
    routing_match = re.search(routing_pattern, response_content, re.IGNORECASE)
    task_match = re.search(task_pattern, response_content, re.IGNORECASE | re.DOTALL)
    
    if routing_match:
        action = routing_match.group(1).upper()
        task = task_match.group(1).strip() if task_match else "No task description provided"
        return {"action": action, "task": task}
    
    # Fallback: if parsing fails, provide direct response
    return {"action": "DIRECT_RESPONSE", "task": response_content}


def search_worker_node(state: OrchestratorState, config: RunnableConfig = None):
    """Search worker node that performs research tasks"""
    model = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL"),
        temperature=0,
        streaming=True,
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        stream_usage=False
    )
    
    tools = get_search_tools()
    search_worker = create_react_agent(
        model,
        tools,
        prompt=lambda state: apply_prompt_template("search_worker", state)
    )
    
    result = search_worker.invoke(state)
    # Update state with search findings
    return {
        **result,
        "search_findings": [result["messages"][-1].content] if result["messages"] else [],
        "workflow_stage": "synthesizing"
    }


def code_worker_node(state: OrchestratorState, config: RunnableConfig = None):
    """Code worker node that handles code execution and analysis"""
    model = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL"),
        temperature=0,
        streaming=True,
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        stream_usage=False
    )
    
    # Get session_id from config which is passed by the session-bound agent
    session_id = config.get("configurable", {}).get("thread_id") if config else "default"
    tools = get_tools(session_id)
    
    code_worker = create_react_agent(
        model,
        tools,
        prompt=lambda state: apply_prompt_template("code_worker", state)
    )
    
    result = code_worker.invoke(state)
    # Update state with code results
    return {
        **result,
        "code_results": [result["messages"][-1].content] if result["messages"] else [],
        "workflow_stage": "synthesizing"
    }