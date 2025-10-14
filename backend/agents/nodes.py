import logging
from langgraph.prebuilt import create_react_agent
from langgraph_swarm import create_swarm, create_handoff_tool

from utils.prompt_loader import apply_prompt_template
from utils.tools import get_search_tools, get_nutritionist_tools, get_coder_tools
from utils.model_config import get_model_config
from core.agent import FormulationState, FormulationSwarmState
from services.session_manager import session_manager

# Configure logging
logger = logging.getLogger(__name__)

async def create_researcher_agent():
    """Create specialized researcher agent for swarm"""
    model = get_model_config("researcher")
    search_tools = get_search_tools()

    # Create handoff tools to other agents in the swarm
    handoff_to_nutritionist = create_handoff_tool(
        agent_name="nutritionist",
        description="Transfer to nutritionist for expert analysis and decision making"
    )
    handoff_to_coder = create_handoff_tool(
        agent_name="coder",
        description="Transfer to coder for calculations, data processing, or file operations"
    )

    all_tools = search_tools + [handoff_to_nutritionist, handoff_to_coder]

    researcher = create_react_agent(
        model=model,
        tools=all_tools,
        state_schema=FormulationState,
        prompt=lambda state: apply_prompt_template("researcher", state),
        name="researcher",
        checkpointer=True,
    )

    return researcher


async def create_coder_agent(animal_type: str = "dairy_cow"):
    """Create specialized coder agent for swarm"""
    model = get_model_config("coder")
    coder_tools = await get_coder_tools(animal_type)

    # Create handoff tools to other agents in the swarm
    handoff_to_nutritionist = create_handoff_tool(
        agent_name="nutritionist",
        description="Transfer to nutritionist for expert analysis and decision making"
    )
    handoff_to_researcher = create_handoff_tool(
        agent_name="researcher",
        description="Transfer to researcher for web research and knowledge base searches"
    )

    all_tools = coder_tools + [handoff_to_nutritionist, handoff_to_researcher]

    coder = create_react_agent(
        model=model,
        tools=all_tools,
        state_schema=FormulationState,
        prompt=lambda state: apply_prompt_template("coder", state),
        name="coder",
        checkpointer=True,
    )

    return coder


async def create_nutritionist_agent(animal_type: str = "dairy_cow"):
    """Create nutritionist agent as peer in swarm"""
    model = get_model_config("nutritionist")
    nutritionist_tools = await get_nutritionist_tools(animal_type)

    # Create handoff tools to other agents in the swarm
    handoff_to_researcher = create_handoff_tool(
        agent_name="researcher",
        description="Transfer to researcher for web research and knowledge base searches"
    )
    handoff_to_coder = create_handoff_tool(
        agent_name="coder",
        description="Transfer to coder for calculations, data processing, or file operations"
    )

    all_tools = nutritionist_tools + [handoff_to_researcher, handoff_to_coder]

    nutritionist = create_react_agent(
        model=model,
        tools=all_tools,
        state_schema=FormulationState,
        prompt=lambda state: apply_prompt_template("nutritionist", state, animal_type),
        name="nutritionist",
        checkpointer=True,
    )

    return nutritionist


async def create_agent_swarm_for_type(animal_type: str):
    """Create the multi-agent swarm for a specific animal type

    Args:
        animal_type: Animal type (dairy_cow, beef_cow, cat, dog)

    Returns:
        Compiled swarm workflow
    """
    # Create all agents as peers in the swarm with specified animal_type
    nutritionist_agent = await create_nutritionist_agent(animal_type)
    researcher_agent = await create_researcher_agent()
    coder_agent = await create_coder_agent(animal_type)

    # Create the swarm with nutritionist as the default active agent
    swarm = create_swarm(
        agents=[nutritionist_agent, researcher_agent, coder_agent],
        default_active_agent="nutritionist",
        handoff_tool_prefix="transfer_to",
        state_schema=FormulationSwarmState
    )

    logger.info(f"Created agent swarm for animal_type: {animal_type} with agents: nutritionist (default), researcher, coder")

    return swarm


