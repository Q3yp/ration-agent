import logging
from langgraph.prebuilt import create_react_agent

from utils.prompt_loader import apply_prompt_template
from tools.tools import get_tools
from utils.model_config import get_model_config
from core.agent import FormulationState

# Configure logging
logger = logging.getLogger(__name__)


async def create_agent(
    animal_type: str = "dairy_cow",
    include_file_tools: bool = False,
    checkpointer=None,
    store=None,
):
    """Create a single react agent for the given animal type.

    Args:
        animal_type: Animal type (dairy_cow, beef_cow, cat, dog)
        include_file_tools: Whether to include file/Excel/bash tools
        checkpointer: LangGraph checkpointer for persistence
        store: LangGraph store for cross-session data

    Returns:
        A compiled LangGraph react agent
    """
    model = get_model_config("nutritionist")
    tools = await get_tools(animal_type, include_file_tools=include_file_tools)

    agent = create_react_agent(
        model=model,
        tools=tools,
        state_schema=FormulationState,
        prompt=lambda state: apply_prompt_template("nutritionist", state, animal_type),
        name="nutritionist",
        checkpointer=checkpointer,
        store=store,
    )

    variant = "full" if include_file_tools else "lite"
    logger.info(f"Created {variant} agent for animal_type: {animal_type} with {len(tools)} tools")

    return agent
