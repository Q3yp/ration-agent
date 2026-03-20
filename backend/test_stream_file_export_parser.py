import time
import sys

from langchain_core.messages import ToolMessage
from langgraph.types import Command

sys.path.insert(0, "backend")

from utils.message_parser import UnifiedMessageParser


def build_event(output, run_id: str = "run123"):
    return {
        "event": "on_tool_end",
        "name": "export_formulation",
        "run_id": run_id,
        "timestamp": time.time(),
        "data": {"output": output},
    }


def assert_single_export(messages, filename: str, filepath: str):
    assert len(messages) == 1, messages
    message = messages[0]
    assert message.type == "file_export", message
    assert message.metadata["filename"] == filename, message
    assert message.metadata["filepath"] == filepath, message


parser = UnifiedMessageParser("session-test")

# Streaming export returned as Command(update={"messages": [ToolMessage(...)]})
apostrophe_msg = ToolMessage(
    content='ok [FILE_EXPORT]{"filepath": "/tmp/a.xlsx", "filename": "b\'s file.xlsx", "type": "excel"}[/FILE_EXPORT]',
    tool_call_id="tool-1",
)
apostrophe_output = Command(update={"messages": [apostrophe_msg]})
apostrophe_messages = parser.parse_streaming_event(build_event(apostrophe_output, "tool-1"))
assert_single_export(apostrophe_messages, "b's file.xlsx", "/tmp/a.xlsx")

# Duplicate nested references to the same exported file should still emit one card.
duplicate_msg = ToolMessage(
    content='ok [FILE_EXPORT]{"filepath": "/tmp/dup.xlsx", "filename": "dup.xlsx", "type": "excel"}[/FILE_EXPORT]',
    tool_call_id="tool-2",
)
duplicate_output = Command(
    update={
        "messages": [duplicate_msg],
        "shadow": {"messages": [duplicate_msg]},
    }
)
duplicate_messages = parser.parse_streaming_event(build_event(duplicate_output, "tool-2"))
assert_single_export(duplicate_messages, "dup.xlsx", "/tmp/dup.xlsx")

print("stream file export parser checks passed")
