import os
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from langgraph.prebuilt.chat_agent_executor import AgentState

# Initialize Jinja2 environment
prompts_dir = Path(__file__).parent.parent / "prompts"
env = Environment(
    loader=FileSystemLoader(str(prompts_dir)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def apply_prompt_template(prompt_name: str, state: AgentState) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.
    
    Args:
        prompt_name: Name of the prompt template to use (supervisor, search_worker, code_worker)
        state: Current agent state containing variables to substitute
        
    Returns:
        List of messages with the system prompt as the first message
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
        template = env.get_template(f"{prompt_name}.md")
        system_prompt = template.render(**state_vars)
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")