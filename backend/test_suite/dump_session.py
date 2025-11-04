#!/usr/bin/env python3
"""
Dump complete session data from database.
Exports messages, metadata, and token usage statistics.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.session_manager import session_manager
from services.chat_history_service import chat_history_service

# Load environment variables so database credentials are available when running as a script
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)


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
    # Ensure session manager is initialized
    await session_manager.initialize()

    try:
        # Fetch session context directly from database
        session_context = await session_manager.get_session_from_db(session_id)

        if not session_context:
            raise ValueError(f"Session {session_id} not found")

        # Get message history from LangGraph checkpointer
        messages = await chat_history_service.get_complete_session_messages(session_id)

        # Fetch session stats (token usage, timestamps, etc.)
        session_stats = await session_manager.get_session_stats(session_id)

        def _get_message_attr(message, attr, default=None):
            if isinstance(message, dict):
                return message.get(attr, default)
            return getattr(message, attr, default)

        def _get_additional_field(message, key, default=None):
            additional = _get_message_attr(message, "additional_kwargs", {}) or {}
            if isinstance(additional, dict):
                return additional.get(key, default)
            return default

        # Extract session metadata
        session_data = {
            "session_id": session_id,
            "user_id": session_context.user_id,
            "animal_type": session_context.animal_type,
            "title": session_context.title if getattr(session_context, "title", None) else "Untitled Session",
            "created_at": session_context.created_at.isoformat() if getattr(session_context, "created_at", None) else None,
            "updated_at": session_context.last_accessed.isoformat() if getattr(session_context, "last_accessed", None) else None,
            "deleted": getattr(session_context, "deleted", False),
            "message_count": len(messages),
            "workspace_path": session_context.workspace_path,
            "title_generated": getattr(session_context, "title_generated", False),
        }

        # Add token usage if available
        token_usage = session_stats.get("token_usage") if isinstance(session_stats, dict) else None
        if token_usage:
            session_data["token_usage"] = {
                "total_prompt_tokens": token_usage.get("prompt_tokens", 0),
                "total_completion_tokens": token_usage.get("completion_tokens", 0),
                "total_tokens": token_usage.get("total_tokens", 0),
            }

        # Process messages
        processed_messages = []
        for msg in messages:
            msg_type = _get_message_attr(msg, "type")
            if not msg_type:
                # Fallback to class name for LangChain message objects
                msg_type = msg.__class__.__name__.replace("Message", "").lower()

            additional_kwargs = _get_message_attr(msg, "additional_kwargs", {}) or {}
            response_metadata = _get_message_attr(msg, "response_metadata", {}) or {}

            msg_data = {
                "content": _get_message_attr(msg, "content", ""),
                "additional_kwargs": additional_kwargs,
                "response_metadata": response_metadata,
                "type": msg_type,
                "name": _get_message_attr(msg, "name"),
                "id": _get_message_attr(msg, "id") or additional_kwargs.get("id"),
                "example": _get_message_attr(msg, "example", False),
            }

            # Add tool calls if present
            tool_calls = _get_message_attr(msg, "tool_calls")
            if tool_calls is None:
                tool_calls = additional_kwargs.get("tool_calls")
            if tool_calls:
                msg_data["tool_calls"] = tool_calls

            # Add invalid tool calls if present
            invalid_tool_calls = _get_message_attr(msg, "invalid_tool_calls")
            if invalid_tool_calls is None:
                invalid_tool_calls = additional_kwargs.get("invalid_tool_calls")
            if invalid_tool_calls:
                msg_data["invalid_tool_calls"] = invalid_tool_calls

            # Add usage metadata if present
            usage_metadata = _get_message_attr(msg, "usage_metadata")
            if usage_metadata is None:
                usage_metadata = additional_kwargs.get("usage_metadata")
            if usage_metadata:
                msg_data["usage_metadata"] = usage_metadata

            # Add tool-specific fields
            if msg_type == "tool":
                tool_call_id = _get_message_attr(msg, "tool_call_id") or additional_kwargs.get("tool_call_id")
                if tool_call_id:
                    msg_data["tool_call_id"] = tool_call_id
                if include_artifacts:
                    artifact = _get_message_attr(msg, "artifact") or additional_kwargs.get("artifact")
                    if artifact:
                        msg_data["artifact"] = artifact
                msg_data["status"] = _get_message_attr(msg, "status", "success")

            processed_messages.append(msg_data)

        # Update message count with processed length (in case of transformations)
        session_data["message_count"] = len(processed_messages)

        # Create summary statistics
        summary = {
            "session_id": session_id,
            "total_messages": len(processed_messages),
            "human_messages": sum(1 for m in processed_messages if m.get("type") == "human"),
            "ai_messages": sum(1 for m in processed_messages if m.get("type") == "ai"),
            "system_messages": sum(1 for m in processed_messages if m.get("type") == "system"),
            "tool_messages": sum(1 for m in processed_messages if m.get("type") == "tool"),
            "has_history": len(processed_messages) > 0,
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
