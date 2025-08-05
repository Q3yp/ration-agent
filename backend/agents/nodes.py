import os
import re
import logging
from typing import Literal, Dict, Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from utils.prompt_loader import apply_prompt_template
from utils.tools import get_tools
from utils.tools import get_search_tools, get_supervisor_tools
from utils.model_config import get_model_config
from core.agent import OrchestratorState

# Configure logging for node message parsing
logger = logging.getLogger(__name__)


class StreamingResponseParser:
    """Handles streaming parsing of <user> and <action> blocks"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset parser state for new response"""
        self.state = "waiting_for_user"  # waiting_for_user, streaming_user, buffering_action, complete
        self.user_content = ""
        self.action_content = ""
        self.buffer = ""
        self.full_response = ""
    
    def parse_chunk(self, chunk: str) -> Dict[str, Any]:
        """
        Parse a streaming chunk with adaptive tag capturing
        """
        # Handle None or non-string chunks
        if chunk is None:
            chunk = ""
        elif not isinstance(chunk, str):
            chunk = str(chunk)
            
        self.buffer += chunk
        self.full_response += chunk
        result = {
            "user_chunk": "",
            "action_data": None,
            "is_complete": False,
            "user_message": self.user_content
        }
        
        
        if self.state == "waiting_for_user":
            if "<user>" in self.buffer:
                # Found start of user block
                parts = self.buffer.split("<user>", 1)
                self.state = "streaming_user"
                self.buffer = parts[1]
        
        if self.state == "streaming_user":
            if "</user>" in self.buffer:
                # Found complete end tag
                parts = self.buffer.split("</user>", 1)
                user_content = parts[0]
                self.user_content += user_content
                result["user_chunk"] = user_content
                result["user_message"] = self.user_content
                
                
                self.state = "waiting_for_user"
                self.buffer = parts[1]
            else:
                # Check if we might have partial closing tag at end
                streamable_content = self.buffer
                potential_tag_start = -1
                
                # Look for partial </user> at the end
                for i in range(1, min(7, len(self.buffer) + 1)):  # </user> is 7 chars
                    partial = self.buffer[-i:]
                    if "</user>".startswith(partial):
                        potential_tag_start = len(self.buffer) - i
                        break
                
                if potential_tag_start >= 0:
                    # Hold back potential partial tag
                    streamable_content = self.buffer[:potential_tag_start]
                    self.buffer = self.buffer[potential_tag_start:]
                else:
                    # No partial tag, stream everything
                    self.buffer = ""
                
                if streamable_content:
                    self.user_content += streamable_content
                    result["user_chunk"] = streamable_content
                    result["user_message"] = self.user_content
        
        # Check for action when not in user block - only emit once when </action> is detected
        if self.state == "waiting_for_user" and self.buffer:
            action_match = re.search(r'<action>(.*?)</action>', self.buffer, re.DOTALL)
            if action_match:
                action_content = action_match.group(1).strip()
                result["action_data"] = self._parse_action_content(action_content)
                result["is_complete"] = True
                # Clear action from buffer to prevent re-processing
                self.buffer = re.sub(r'<action>.*?</action>', '', self.buffer, flags=re.DOTALL)
        
        return result
    
    def _parse_action_content(self, content: str) -> Dict[str, str]:
        """Parse action content like 'route:supervisor, finding:research completed'"""
        action_data = {}
        # Split by comma and parse key:value pairs
        for item in content.split(','):
            if ':' in item:
                key, value = item.split(':', 1)
                action_data[key.strip()] = value.strip()
        return action_data


async def supervisor_node(state: OrchestratorState, config: RunnableConfig = None) -> Command[Literal["researcher", "coder", "__end__"]]:
    """Supervisor node that analyzes requests and routes to appropriate workers"""
    # Get model using centralized configuration
    model = get_model_config("supervisor")
    
    # Get session_id from config to create session-bound artifact tools
    session_id = config["configurable"]["thread_id"]
    
    # Get supervisor tools (artifact creation and listing + Excel tools)
    supervisor_tools = await get_supervisor_tools(session_id)
    
    supervisor = create_react_agent(
        model,
        supervisor_tools,
        prompt=lambda state: apply_prompt_template("supervisor", state)
    )
    
    # Invoke the supervisor agent
    result = await supervisor.ainvoke(state, config)
    
    # Parse the response using new format
    if result.get("messages"):
        last_message = result["messages"][-1]
        if hasattr(last_message, 'content'):
            parser = StreamingResponseParser()
            parsed = parser.parse_chunk(last_message.content)
            
            action_data = parsed.get("action_data")
            if action_data is None:
                action_data = {}
            route = action_data.get("route", "").lower()
            
            # Store parsed response for frontend
            result["parsed_response"] = {
                "user_message": parsed["user_message"],
                "action_data": action_data,
                "full_response": last_message.content
            }
            
            # Route based on action data
            if route == "researcher":
                return Command(
                    update={
                        **result,
                        "current_task": action_data.get("task", ""),
                        "assigned_worker": "researcher",
                        "workflow_stage": "working"
                    },
                    goto="researcher"
                )
            elif route == "coder":
                return Command(
                    update={
                        **result,
                        "current_task": action_data.get("task", ""),
                        "assigned_worker": "coder",
                        "workflow_stage": "working"
                    },
                    goto="coder"
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


async def researcher_node(state: OrchestratorState, config: RunnableConfig = None):
    """Researcher node that performs research tasks"""
    # Get model using centralized configuration
    model = get_model_config("researcher")
    
    tools = get_search_tools()
    researcher = create_react_agent(
        model,
        tools,
        prompt=lambda state: apply_prompt_template("researcher", state)
    )
    
    result = await researcher.ainvoke(state, config)
    
    # Parse the response to extract user message and action
    if result.get("messages"):
        last_message = result["messages"][-1]
        if hasattr(last_message, 'content'):
            parser = StreamingResponseParser()
            # For non-streaming use, process full content at once
            parsed = parser.parse_chunk(last_message.content)
            
            # Extract action data
            action_data = parsed.get("action_data")
            if action_data is None:
                action_data = {}
            
            return {
                **result,
                "search_findings": [action_data.get("finding", parsed["user_message"])],
                "workflow_stage": "synthesizing",
                "parsed_response": {
                    "user_message": parsed["user_message"],
                    "action_data": action_data,
                    "full_response": last_message.content
                }
            }
    
    # Fallback for no messages
    return {
        **result,
        "search_findings": [],
        "workflow_stage": "synthesizing"
    }


async def coder_node(state: OrchestratorState, config: RunnableConfig = None):
    """Coder node that handles code execution and analysis"""
    # Get model using centralized configuration
    model = get_model_config("coder")
    
    # Get session_id from config which is passed by the session-bound agent
    session_id = config["configurable"]["thread_id"]
    tools = await get_tools(session_id)
    
    coder = create_react_agent(
        model,
        tools,
        prompt=lambda state: apply_prompt_template("coder", state)
    )
    
    result = await coder.ainvoke(state, config)
    
    # Parse the response to extract user message and action
    if result.get("messages"):
        last_message = result["messages"][-1]
        if hasattr(last_message, 'content'):
            parser = StreamingResponseParser()
            # For non-streaming use, process full content at once
            parsed = parser.parse_chunk(last_message.content)
            
            # Extract action data
            action_data = parsed.get("action_data")
            if action_data is None:
                action_data = {}
            
            return {
                **result,
                "code_results": [action_data.get("finding", parsed["user_message"])],
                "workflow_stage": "synthesizing",
                "parsed_response": {
                    "user_message": parsed["user_message"],
                    "action_data": action_data,
                    "full_response": last_message.content
                }
            }
    
    # Fallback for no messages
    return {
        **result,
        "code_results": [],
        "workflow_stage": "synthesizing"
    }