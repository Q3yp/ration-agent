import os
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from core.agent import FormulationState

# Initialize Jinja2 environment
prompts_dir = Path(__file__).parent.parent / "prompts"
env = Environment(
    loader=FileSystemLoader(str(prompts_dir)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


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
        
        # Role-based message isolation
        if prompt_name == "nutritionist":
            # Nutritionist gets full conversation context
            agent_messages = state.get("messages", [])
        elif prompt_name == "researcher":
            # Researcher only gets task-based messages if available, otherwise full context
            agent_messages = state.get("researcher_messages", state.get("messages", []))
        elif prompt_name == "coder":
            # Coder only gets task-based messages if available, otherwise full context
            agent_messages = state.get("coder_messages", state.get("messages", []))
        else:
            # Fallback to original behavior for unknown agents
            agent_messages = state.get("messages", [])
        
        return [{"role": "system", "content": system_prompt}] + agent_messages
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")