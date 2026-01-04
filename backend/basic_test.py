import os
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import tool, InjectedToolCallId
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.types import Command
from langgraph.graph import StateGraph, START, END

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

USER_INFO = [
    {"user_id": "1", "name": "Bob Dylan", "location": "New York, NY"},
    {"user_id": "2", "name": "Taylor Swift", "location": "Beverly Hills, CA"},
]

USER_ID_TO_USER_INFO = {info["user_id"]: info for info in USER_INFO}


class State(AgentState):
    # updated by the tool
    user_info: dict[str, Any]


async def main() -> None:
    @tool
    def lookup_user_info(tool_call_id: Annotated[str, InjectedToolCallId], config: RunnableConfig):
        """Use this to look up user information to better assist them with their questions."""
        user_id = config.get("configurable", {}).get("user_id")
        if user_id is None:
            raise ValueError("Please provide user ID")

        if user_id not in USER_ID_TO_USER_INFO:
            raise ValueError(f"User '{user_id}' not found")

        user_info = USER_ID_TO_USER_INFO[user_id]
        return Command(
            update={
                # update the state keys
                "user_info": user_info,
                # update the message history
                "messages": [
                    ToolMessage(
                        "Successfully looked up user information", tool_call_id=tool_call_id
                    )
                ],
            }
        )

    def prompt(state: State):
        user_info = state.get("user_info")
        if user_info is None:
            return state["messages"]

        system_msg = (
            f"User name is {user_info['name']}. User lives in {user_info['location']}"
        )
        return [{"role": "system", "content": system_msg}] + state["messages"]

    model = ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "deepseek-chat"),
        temperature=0.0,
        openai_api_base=os.getenv("OPENAI_ENDPOINT"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    # Create the react agent as a node function
    async def agent_node(state: State, config: RunnableConfig = None):
        """Node that uses create_react_agent internally"""
        agent = create_react_agent(
            model,
            # pass the tool that can update state
            [lookup_user_info],
            state_schema=State,
            # pass dynamic prompt function
            prompt=prompt,
        )
        
        # Call the agent and return result
        result = await agent.ainvoke(state, config)
        return result
    
    # Create the main graph
    builder = StateGraph(State)
    builder.add_node("agent", agent_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    
    graph = builder.compile()

    agent_input = {"messages": [("user", "hi, where do I live?")]}
    agent_config = {"configurable": {"user_id": "1"}}

    # Test with a more explicit prompt that forces tool use
    agent_input = {"messages": [("user", "Use the lookup_user_info tool to get my information and tell me where I live")]}
    
    # Test with streaming to catch thinking chunks
    print("=== TESTING WITH STREAMING ===")
    final_state = None
    async for event in graph.astream(agent_input, agent_config):
        print(f"Event: {event}")
        if "agent" in event:
            final_state = event["agent"]
    
    invoke_result = final_state or await graph.ainvoke(agent_input, agent_config)

    print("=== FINAL RESULT (Graph Node Test) ===")
    print(f"user_info in state: {invoke_result.get('user_info', 'NOT FOUND')}")
    print(f"Messages: {len(invoke_result.get('messages', []))}")
    
    # Check for thinking chunks in messages
    print("\n=== CHECKING FOR THINKING CHUNKS ===")
    for i, msg in enumerate(invoke_result.get('messages', [])):
        print(f"Message {i}: Type={type(msg).__name__}")
        if hasattr(msg, 'additional_kwargs'):
            print(f"  additional_kwargs: {msg.additional_kwargs}")
            if 'reasoning_content' in msg.additional_kwargs:
                print(f"  🧠 THINKING FOUND in additional_kwargs: {msg.additional_kwargs['reasoning_content'][:100]}...")
        if hasattr(msg, 'response_metadata'):
            print(f"  response_metadata: {msg.response_metadata}")
            if 'reasoning_content' in msg.response_metadata:
                print(f"  🧠 THINKING FOUND in response_metadata: {msg.response_metadata['reasoning_content'][:100]}...")
        if hasattr(msg, 'content'):
            print(f"  content: {msg.content[:100]}...")
        print()
    
    # Test if state was updated by Command
    if invoke_result.get('user_info'):
        print("✅ SUCCESS: Command object worked in graph node - user_info was updated!")
        print(f"User info: {invoke_result['user_info']}")
    else:
        print("❌ FAILED: Command object did not update state in graph node")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())