#!/usr/bin/env python3
"""Analyze session state for prompt caching optimization."""
import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv()

import tiktoken
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

SESSION_ID = "3f45a25b-981e-4072-bcba-6021f039f15b"

# Token counter
enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

def format_size(chars: int) -> str:
    if chars > 1000:
        return f"{chars/1000:.1f}K chars"
    return f"{chars} chars"

async def main():
    conn_string = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        # Get the latest checkpoint
        config = {"configurable": {"thread_id": SESSION_ID}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        
        if not checkpoint_tuple:
            print(f"No checkpoint found for session {SESSION_ID}")
            return
        
        checkpoint = checkpoint_tuple.checkpoint
        messages = checkpoint.get("channel_values", {}).get("messages", [])
        
        print(f"\n{'='*60}")
        print(f"SESSION: {SESSION_ID}")
        print(f"Total messages: {len(messages)}")
        print(f"{'='*60}\n")
        
        total_tokens = 0
        message_stats = []
        
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content = getattr(msg, 'content', '')
            
            # Handle different content types
            if isinstance(content, list):
                content_str = json.dumps(content, ensure_ascii=False)
            else:
                content_str = str(content) if content else ""
            
            tokens = count_tokens(content_str)
            total_tokens += tokens
            
            # Get tool call info if present
            tool_calls = getattr(msg, 'tool_calls', None)
            tool_name = ""
            if tool_calls:
                tool_name = ", ".join([tc.get('name', 'unknown') for tc in tool_calls])
            
            # For ToolMessage, get the name
            if msg_type == "ToolMessage":
                tool_name = getattr(msg, 'name', 'unknown')
            
            message_stats.append({
                'idx': i,
                'type': msg_type,
                'tool': tool_name,
                'tokens': tokens,
                'chars': len(content_str),
                'preview': content_str[:80].replace('\n', ' ') if content_str else "(empty)"
            })
        
        # Sort by token count
        sorted_stats = sorted(message_stats, key=lambda x: x['tokens'], reverse=True)
        
        print("TOP 15 HEAVIEST MESSAGES (by tokens):")
        print("-" * 80)
        for stat in sorted_stats[:15]:
            tool_info = f" [{stat['tool']}]" if stat['tool'] else ""
            print(f"#{stat['idx']:3d} {stat['type']:15s}{tool_info:30s} | {stat['tokens']:6d} tokens | {stat['preview'][:40]}...")
        
        print(f"\n{'='*60}")
        print(f"TOTAL CONVERSATION TOKENS: {total_tokens:,}")
        print(f"{'='*60}")
        
        # Group by message type
        print("\nBY MESSAGE TYPE:")
        type_totals = {}
        for stat in message_stats:
            key = stat['type']
            if key not in type_totals:
                type_totals[key] = {'count': 0, 'tokens': 0}
            type_totals[key]['count'] += 1
            type_totals[key]['tokens'] += stat['tokens']
        
        for msg_type, data in sorted(type_totals.items(), key=lambda x: x[1]['tokens'], reverse=True):
            print(f"  {msg_type:20s}: {data['count']:3d} msgs, {data['tokens']:6d} tokens")
        
        # Group by tool name for ToolMessages
        print("\nTOOL MESSAGE BREAKDOWN:")
        tool_totals = {}
        for stat in message_stats:
            if stat['type'] == 'ToolMessage' and stat['tool']:
                key = stat['tool']
                if key not in tool_totals:
                    tool_totals[key] = {'count': 0, 'tokens': 0}
                tool_totals[key]['count'] += 1
                tool_totals[key]['tokens'] += stat['tokens']
        
        for tool, data in sorted(tool_totals.items(), key=lambda x: x[1]['tokens'], reverse=True):
            print(f"  {tool:35s}: {data['count']:3d} calls, {data['tokens']:6d} tokens")

if __name__ == "__main__":
    asyncio.run(main())
