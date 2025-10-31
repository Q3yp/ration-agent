#!/usr/bin/env python3
"""
Dump complete session data from database.
Exports messages, metadata, and token usage statistics.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import UserSession, SessionMessage
from services.session_manager import SessionManager
from core.agent import get_shared_connection


async def dump_session(
    session_id: str,
    output_dir: Optional[Path] = None,
    include_artifacts: bool = True
) -> dict:
    """
    Dump complete session data to JSON file.

    Args:
        session_id: UUID of the session to dump
        output_dir: Directory to save output (default: current directory)
        include_artifacts: Whether to include artifact data

    Returns:
        Dictionary containing session data
    """
    # Get database connection
    conn = await get_shared_connection()

    # Create session manager
    session_manager = SessionManager(conn)

    try:
        # Get session context
        session_context = await session_manager.get_session_context(session_id)

        if not session_context:
            raise ValueError(f"Session {session_id} not found")

        # Get message history
        messages = await session_manager.get_message_history(session_id)

        # Extract session metadata
        session_data = {
            "session_id": session_id,
            "user_id": session_context.get("user_id"),
            "animal_type": session_context.get("animal_type", "unknown"),
            "title": session_context.get("title", "Untitled Session"),
            "created_at": session_context.get("created_at"),
            "updated_at": session_context.get("updated_at"),
            "deleted": session_context.get("deleted", False),
            "message_count": len(messages),
        }

        # Add token usage if available
        if "total_tokens" in session_context:
            session_data["token_usage"] = {
                "total_prompt_tokens": session_context.get("total_prompt_tokens", 0),
                "total_completion_tokens": session_context.get("total_completion_tokens", 0),
                "total_tokens": session_context.get("total_tokens", 0),
            }

        # Process messages
        processed_messages = []
        for msg in messages:
            msg_data = {
                "content": msg.get("content", ""),
                "additional_kwargs": msg.get("additional_kwargs", {}),
                "response_metadata": msg.get("response_metadata", {}),
                "type": msg.get("type", ""),
                "name": msg.get("name"),
                "id": msg.get("id"),
                "example": msg.get("example", False),
            }

            # Add tool calls if present
            if "tool_calls" in msg:
                msg_data["tool_calls"] = msg["tool_calls"]

            # Add invalid tool calls if present
            if "invalid_tool_calls" in msg:
                msg_data["invalid_tool_calls"] = msg["invalid_tool_calls"]

            # Add usage metadata if present
            if "usage_metadata" in msg:
                msg_data["usage_metadata"] = msg["usage_metadata"]

            # Add tool-specific fields
            if msg.get("type") == "tool":
                msg_data["tool_call_id"] = msg.get("tool_call_id")
                if include_artifacts and "artifact" in msg:
                    msg_data["artifact"] = msg["artifact"]
                msg_data["status"] = msg.get("status", "success")

            processed_messages.append(msg_data)

        # Create summary statistics
        summary = {
            "session_id": session_id,
            "total_messages": len(messages),
            "human_messages": sum(1 for m in messages if m.get("type") == "human"),
            "ai_messages": sum(1 for m in messages if m.get("type") == "ai"),
            "system_messages": sum(1 for m in messages if m.get("type") == "system"),
            "tool_messages": sum(1 for m in messages if m.get("type") == "tool"),
            "has_history": len(messages) > 0,
        }

        # Combine all data
        dump_data = {
            **session_data,
            "summary": summary,
            "messages": processed_messages,
        }

        # Save to file if output_dir specified
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{session_id}_messages.json"

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(dump_data, f, indent=2, ensure_ascii=False, default=str)

            print(f"✓ Session dumped to: {output_file}")

            # Calculate and save token statistics
            if "token_usage" in session_data:
                stats_file = output_dir / f"{session_id}_stats.txt"
                with open(stats_file, 'w', encoding='utf-8') as f:
                    f.write(f"Session: {session_id}\n")
                    f.write(f"Title: {session_data['title']}\n")
                    f.write(f"Animal Type: {session_data['animal_type']}\n")
                    f.write(f"Messages: {len(messages)}\n")
                    f.write(f"\nToken Usage:\n")
                    f.write(f"  Input tokens:  {session_data['token_usage']['total_prompt_tokens']:,}\n")
                    f.write(f"  Output tokens: {session_data['token_usage']['total_completion_tokens']:,}\n")
                    f.write(f"  Total tokens:  {session_data['token_usage']['total_tokens']:,}\n")

                print(f"✓ Statistics saved to: {stats_file}")

        return dump_data

    except Exception as e:
        print(f"✗ Error dumping session {session_id}: {e}")
        raise

    finally:
        # Close connection if we created it
        if conn:
            await conn.close()


async def main():
    """Main entry point for command line usage"""
    if len(sys.argv) < 2:
        print("Usage: python dump_session.py <session_id> [output_directory]")
        print("\nExample:")
        print("  python dump_session.py 5c65b644-e527-4c2d-ad53-30d623f9728a")
        print("  python dump_session.py 5c65b644-e527-4c2d-ad53-30d623f9728a ./test_runs/20251030_120000")
        sys.exit(1)

    session_id = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")

    print(f"Dumping session: {session_id}")
    print(f"Output directory: {output_dir}")
    print()

    try:
        await dump_session(session_id, output_dir)
        print("\n✅ Session dump completed successfully")
    except Exception as e:
        print(f"\n❌ Session dump failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
