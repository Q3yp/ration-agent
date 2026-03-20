import os
from pathlib import Path
from datetime import datetime
from typing import List, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from core.agent import FormulationState

# Initialize Jinja2 environment
prompts_dir = Path(__file__).parent.parent / "prompts"
env = Environment(
    loader=FileSystemLoader(str(prompts_dir)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _is_anthropic_model() -> bool:
    """Check if the current model configuration uses Anthropic/Claude models via OpenRouter."""
    model = os.getenv("NUTRITIONIST_MODEL", os.getenv("OPENROUTER_MODEL", "")).lower()
    
    # Check model name for Anthropic identifiers (OpenRouter uses anthropic/ prefix)
    return "anthropic" in model or "claude" in model


def add_cache_control_to_messages(messages: List[Any]) -> List[Any]:
    """
    Add cache_control to conversation messages for Anthropic prompt caching.
    
    Strategy:
    1. Find the last HumanMessage - this is the stable anchor point
    2. Optionally mark the second-to-last message for multi-tool-call optimization
    
    This creates a sliding cache window that benefits subsequent tool calls
    in a single turn.
    """
    if not messages or len(messages) < 2:
        return messages
    
    # Find indices for cache breakpoints
    last_human_idx = None
    second_to_last_idx = None
    
    # Find the last HumanMessage
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if isinstance(msg, HumanMessage):
            last_human_idx = i
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_human_idx = i
            break
    
    # For multi-tool chains, also mark second-to-last message (if > 3 messages)
    if len(messages) >= 4:
        second_to_last_idx = len(messages) - 2
    
    # Apply cache_control to identified messages
    result = []
    for i, msg in enumerate(messages):
        should_cache = (i == last_human_idx) or (i == second_to_last_idx and second_to_last_idx != last_human_idx)
        
        if should_cache:
            cached_msg = _add_cache_control_to_message(msg)
            result.append(cached_msg)
        else:
            result.append(msg)
    
    return result


def _add_cache_control_to_message(msg: Any) -> Any:
    """Add cache_control to a single message, handling different formats."""
    cache_control = {"type": "ephemeral"}
    
    # Handle dict-style messages
    if isinstance(msg, dict):
        content = msg.get("content", "")
        if isinstance(content, str):
            return {
                **msg,
                "content": [
                    {"type": "text", "text": content, "cache_control": cache_control}
                ]
            }
        elif isinstance(content, list):
            # Already has content blocks, add cache_control to last block
            new_content = content.copy()
            if new_content:
                last_block = new_content[-1].copy()
                last_block["cache_control"] = cache_control
                new_content[-1] = last_block
            return {**msg, "content": new_content}
        return msg
    
    # Handle LangChain BaseMessage objects
    if isinstance(msg, BaseMessage):
        content = msg.content
        if isinstance(content, str):
            # Convert to content block format with cache_control
            new_msg = msg.model_copy()
            new_msg.content = [
                {"type": "text", "text": content, "cache_control": cache_control}
            ]
            return new_msg
        elif isinstance(content, list):
            # Already has content blocks
            new_msg = msg.model_copy()
            new_content = [block.copy() if isinstance(block, dict) else block for block in content]
            if new_content and isinstance(new_content[-1], dict):
                new_content[-1]["cache_control"] = cache_control
            new_msg.content = new_content
            return new_msg
    
    return msg


def apply_prompt_template(prompt_name: str, state: FormulationState, animal_type: str = "dairy_cow") -> list:
    """
    Apply template variables to a prompt template and return formatted messages with role isolation.

    Args:
        prompt_name: Name of the prompt template to use (nutritionist, researcher, coder)
        state: Current agent state containing variables to substitute
        animal_type: Animal type for nutritionist prompt selection (default: dairy_cow)

    Returns:
        List of messages with the system prompt as the first message and agent-specific message history
    """
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S"),
        "workflow_stage": state.get("workflow_stage", "analyzing"),
        "current_task": state.get("current_task", ""),
        "assigned_worker": state.get("assigned_worker", ""),
        "search_findings": state.get("search_findings", []),
        "code_results": state.get("code_results", []),
        "task_context": state.get("task_context", {}),
        **state,
    }
    
    try:
        # For nutritionist, select file based on animal_type
        if prompt_name == "nutritionist":
            template_file = f"nutritionist_{animal_type}.md"
        else:
            template_file = f"{prompt_name}.md"

        template = env.get_template(template_file)
        system_prompt = template.render(**state_vars)
        
        # Single agent — always use full conversation context
        agent_messages = state.get("messages", [])
        
        # Check if using Anthropic/Claude (supports cache_control)
        use_cache_control = _is_anthropic_model()
        
        if use_cache_control:
            # Format system message with cache_control for Anthropic prompt caching
            system_message = {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            }
            # Apply cache_control to conversation history for multi-tool-call optimization
            final_messages = add_cache_control_to_messages(list(agent_messages))
        else:
            # For non-Anthropic models (DeepSeek, OpenAI, etc.), use simple format
            system_message = {
                "role": "system",
                "content": system_prompt
            }
            final_messages = list(agent_messages)
        
        return [system_message] + final_messages
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")