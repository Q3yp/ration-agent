import json
from langgraph.types import Command
from langchain_core.messages import ToolMessage

def extract_content(output):
    if hasattr(output, 'content'):
        return str(output.content)
    elif hasattr(output, 'update') and isinstance(output.update, dict):
        messages = output.update.get("messages", [])
        if messages and hasattr(messages[0], 'content'):
            return str(messages[0].content)
    return str(output)

success_msg = "test [FILE_EXPORT]{\"filepath\": \"a\", \"filename\": \"b\", \"type\": \"excel\"}[/FILE_EXPORT]"
cmd = Command(update={"messages": [ToolMessage(content=success_msg, tool_call_id="123")]})

print(extract_content(cmd))
print(extract_content(ToolMessage(content="hello", tool_call_id="1")))
print(extract_content("raw string"))

