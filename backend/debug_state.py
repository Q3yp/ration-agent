#!/usr/bin/env python3
"""
Debug script to load and analyze session state for message routing issues
"""

import os
import sys
import asyncio
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.agent import create_agent_for_session, FormulationState
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import StateSnapshot
import json
from datetime import datetime


def print_message_details(messages, label):
    """Print detailed information about messages"""
    print(f"\n=== {label} ===")
    print(f"Count: {len(messages)}")
    
    for i, msg in enumerate(messages):
        print(f"\n  [{i}] Type: {type(msg).__name__}")
        if hasattr(msg, 'content'):
            content = msg.content
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"      Content: {repr(content)}")
        if hasattr(msg, 'id'):
            print(f"      ID: {msg.id}")
        if hasattr(msg, 'type'):
            print(f"      Message Type: {msg.type}")


def analyze_state_messages(state: dict):
    """Analyze all message-related fields in the state"""
    print("\n" + "="*80)
    print("STATE MESSAGE ANALYSIS")
    print("="*80)
    
    # Main messages field
    main_messages = state.get("messages", [])
    print_message_details(main_messages, "MAIN MESSAGES")
    
    # Role-specific message threads
    nutritionist_messages = state.get("nutritionist_messages", [])
    print_message_details(nutritionist_messages, "NUTRITIONIST MESSAGES")
    
    researcher_messages = state.get("researcher_messages", [])
    print_message_details(researcher_messages, "RESEARCHER MESSAGES")
    
    coder_messages = state.get("coder_messages", [])
    print_message_details(coder_messages, "CODER MESSAGES")
    
    # Workflow info
    print(f"\n=== WORKFLOW INFO ===")
    print(f"Workflow Stage: {state.get('workflow_stage')}")
    print(f"Processed Message Count: {state.get('processed_message_count')}")
    
    # Task context
    task_context = state.get("task_context", {})
    print(f"\n=== TASK CONTEXT ===")
    print(f"Keys: {list(task_context.keys())}")
    
    # Artifacts
    artifacts = state.get("artifacts", [])
    print(f"\n=== ARTIFACTS ===")
    print(f"Count: {len(artifacts)}")
    

async def debug_session_state(session_id: str):
    """Load and debug session state"""
    print(f"Debugging session: {session_id}")
    print(f"Timestamp: {datetime.now()}")
    
    try:
        # Create agent to get access to checkpointer
        agent = await create_agent_for_session(session_id)
        
        # Get current state
        config = {"configurable": {"thread_id": session_id}}
        
        # Get state snapshot
        state_snapshot = await agent.aget_state(config)
        
        if state_snapshot:
            print(f"\nState retrieved successfully!")
            print(f"Next nodes: {state_snapshot.next}")
            print(f"Config: {state_snapshot.config}")
            
            # Analyze the state values
            analyze_state_messages(state_snapshot.values)
            
            # Check state history
            print(f"\n=== STATE HISTORY ===")
            history = []
            async for state_history in agent.aget_state_history(config):
                history.append(state_history)
            
            print(f"Total state snapshots in history: {len(history)}")
            
            # Show last few snapshots
            for i, snapshot in enumerate(history[:3]):  # Last 3 snapshots
                print(f"\nSnapshot [{i}]:")
                print(f"  Next: {snapshot.next}")
                print(f"  Created: {snapshot.created_at}")
                print(f"  Main messages count: {len(snapshot.values.get('messages', []))}")
                print(f"  Workflow stage: {snapshot.values.get('workflow_stage')}")
                
                # Show recent messages in this snapshot
                messages = snapshot.values.get('messages', [])
                if messages:
                    print(f"  Last message type: {type(messages[-1]).__name__}")
                    if hasattr(messages[-1], 'content'):
                        content = messages[-1].content[:100] + "..." if len(messages[-1].content) > 100 else messages[-1].content
                        print(f"  Last message content: {repr(content)}")
            
        else:
            print("No state found for this session")
            
    except Exception as e:
        print(f"Error loading session state: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function"""
    session_id = "d0dd8b35-e426-4190-89fb-227487860391"
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Debug session state
    await debug_session_state(session_id)


if __name__ == "__main__":
    asyncio.run(main())