import os
import re
import logging
from typing import Literal, Dict, Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.types import Command, interrupt
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES


from utils.prompt_loader import apply_prompt_template
from utils.tools import get_tools
from utils.tools import get_search_tools, get_nutritionist_tools
from utils.model_config import get_model_config
from utils.stop_manager import StopManager
from core.agent import FormulationState

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
      """Parse structured action with route and task/finding fields"""
      action_data = {}

      # Extract route (simple word)
      route_match = re.search(r'route:\s*(\w+)', content)
      if route_match:
          action_data['route'] = route_match.group(1).strip()

      # Extract task (everything after "task:")
      task_match = re.search(r'task:\s*(.+)', content, re.DOTALL)
      if task_match:
          action_data['task'] = task_match.group(1).strip()

      # Extract finding (everything after "finding:")  
      finding_match = re.search(r'finding:\s*(.+)', content, re.DOTALL)
      if finding_match:
          action_data['finding'] = finding_match.group(1).strip()

      return action_data


async def pre_model_hook(state: FormulationState):
    cur_node = state.get('workflow_stage', 'nutritionist')  # Default to nutritionist
    logger.info(state.get('workflow_stage'))
    # Get the base messages for current workflow stage
    base_messages = state.get(cur_node + "_messages", [])
    all_messages = state.get("messages", [])
    
    # Check if there are new messages to distribute to current node
    processed_count = state.get("processed_message_count", 0)
    current_count = len(all_messages)
    
    if current_count > processed_count:
        # Get new messages since last processing
        new_messages = all_messages[processed_count:]
        updated_messages = base_messages + new_messages
        
        return {
            "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES),*updated_messages],
            cur_node + "_messages": new_messages,  # Append new messages to current node
            "processed_message_count": current_count  # Update tracker
        }
    
    
    # No new messages, return current role messages
    return {"llm_input_messages": base_messages}



async def nutritionist_node(state: FormulationState, config: RunnableConfig = None) -> Command[Literal["researcher", "coder", "__end__"]]:
    """Nutritionist node that analyzes requests and routes to appropriate workers"""
    # Get session_id from config
    session_id = config["configurable"]["thread_id"]
    
    # Check workflow stage - only route if explicitly set to worker nodes
    workflow_stage = state.get("workflow_stage")
    logger.info(f"NODE: Nutritionist node - current workflow_stage: {workflow_stage}")
    
    if workflow_stage == "researcher":
        logger.info(f"NODE: Routing to researcher based on workflow_stage")
        return Command(goto="researcher")
    elif workflow_stage == "coder":
        logger.info(f"NODE: Routing to coder based on workflow_stage") 
        return Command(goto="coder")
    
    # Get model using centralized configuration
    model = get_model_config("nutritionist")
    
    # Get nutritionist tools (artifact creation and listing + Excel tools)
    nutritionist_tools = await get_nutritionist_tools(session_id)
    
    nutritionist = create_react_agent(
        model,
        nutritionist_tools,
        state_schema=FormulationState,
        pre_model_hook=pre_model_hook,
        prompt=lambda state: apply_prompt_template("nutritionist", state),
    )
    
    # Invoke the nutritionist agent
    result = await nutritionist.ainvoke(state, config)
    
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
                # Create isolated task message for researcher (no user context)
                delegation_message = SystemMessage(content="You are receiving a task from the nutritionist supervisor.")
                task_message = AIMessage(content=action_data.get("task", ""))
                count = state.get("processed_message_count", 0)
                
                return Command(
                    update={
                        **result,  # Preserves existing messages field
                        "messages": result["messages"],
                        "workflow_stage": "researcher",
                        "researcher_messages": [delegation_message, task_message],  # Isolated context for researcher
                        "processed_message_count": count+2
                    },
                    goto="researcher"
                )
            elif route == "coder":
                # Create isolated task message for coder (no user context)
                delegation_message = SystemMessage(content="You are receiving a task from the nutritionist supervisor.")
                task_message = AIMessage(content=action_data.get("task", ""))
                count = state.get("processed_message_count", 0)
                
                return Command(
                    update={
                        **result,  # Preserves existing messages field
                        "workflow_stage": "coder",
                        "coder_messages": [delegation_message, task_message], # Isolated context for coder
                        "processed_message_count": count+2 
                    },
                    goto="coder"
                )
    
    # Default: end the conversation with nutritionist's response
    return Command(
        update={**result, "workflow_stage": "completed"},
        goto="__end__"
    )


def _parse_nutritionist_response(response_content: str) -> dict:
    """Parse nutritionist LLM response to extract routing decision"""
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


async def researcher_node(state: FormulationState, config: RunnableConfig = None):
    """Researcher node that performs research tasks"""
    # Get session_id from config
    session_id = config["configurable"]["thread_id"]
    
    # Get model using centralized configuration
    model = get_model_config("researcher")
    
    tools = get_search_tools()
    researcher = create_react_agent(
        model,
        tools,
        state_schema=FormulationState,
        pre_model_hook=pre_model_hook,
        prompt=lambda state: apply_prompt_template("researcher", state),
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
            
            # Send response back to nutritionist with role indication
            response_message = SystemMessage(content="Response from researcher agent:")
            result_message = AIMessage(content=action_data.get("finding", parsed["user_message"]))
            
            # All result messages are new from this node's execution
            new_messages = result["messages"]  # All messages from this node
            
            # Update processed count: previous state messages + new messages from this node
            state_message_count = len(state.get("messages", []))
            new_processed_count = state_message_count + len(new_messages)
            
            return Command(
                update={
                    **result,  # Add to main message history
                    "workflow_stage": "nutritionist",
                    "researcher_messages": new_messages,  # Add NEW messages to researcher thread
                    "nutritionist_messages": [response_message, result_message],
                    "processed_message_count": new_processed_count,  # Update processed count
                    "parsed_response": {
                        "user_message": parsed["user_message"],
                        "action_data": action_data,
                        "full_response": last_message.content
                    }
                },
                goto="nutritionist"
            )
    
    # Fallback for no messages - already handled above
    return {
        **result,
        "workflow_stage": "nutritionist"
    }


async def coder_node(state: FormulationState, config: RunnableConfig = None):
    """Coder node that handles code execution and analysis"""
    # Get session_id from config
    session_id = config["configurable"]["thread_id"]
    
    # Get model using centralized configuration
    model = get_model_config("coder")
    
    # Get tools for the session
    tools = await get_tools(session_id)
    
    coder = create_react_agent(
        model,
        tools,
        state_schema=FormulationState,
        pre_model_hook=pre_model_hook,
        prompt=lambda state: apply_prompt_template("coder", state),
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
            
            # Send response back to nutritionist with role indication
            response_message = SystemMessage(content="Response from coder agent:")
            result_message = AIMessage(content=action_data.get("finding"))
            
            # All result messages are new from this node's execution
            new_messages = result["messages"]  # All messages from this node
            
            # Update processed count: previous state messages + new messages from this node
            state_message_count = len(state.get("messages", []))
            new_processed_count = state_message_count + len(new_messages)
            
            return Command(
                update={
                    **result,  # Add to main message history
                    "workflow_stage": "nutritionist", 
                    "coder_messages": new_messages,  # Add NEW messages to coder thread
                    "nutritionist_messages": [response_message, result_message],
                    "processed_message_count": new_processed_count,  # Update processed count
                    "parsed_response": {
                        "user_message": parsed["user_message"],
                        "action_data": action_data,
                        "full_response": last_message.content
                    }
                },
                goto="nutritionist"
            )
    
    # Fallback for no messages - use last message from researcher
    if result.get("messages"):
        last_message = result["messages"][-1]
        response_message = SystemMessage(content="Response from researcher agent:")
        result_message = AIMessage(content=last_message.content if hasattr(last_message, 'content') else str(last_message))
        
        return {
            **result,
            "workflow_stage": "nutritionist",
            "nutritionist_messages": [response_message, result_message]
        }
    
    return {
        **result,
        "workflow_stage": "nutritionist"
    }