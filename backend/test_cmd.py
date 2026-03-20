from langgraph.types import Command
from langchain_core.messages import ToolMessage

success_msg = "test [FILE_EXPORT]{\"filepath\": \"a\", \"filename\": \"b\", \"type\": \"excel\"}[/FILE_EXPORT]"
cmd = Command(update={"messages": [ToolMessage(content=success_msg, tool_call_id="123")]})

print(type(cmd))
print(hasattr(cmd, 'update'))
print(cmd.update)
print(str(cmd).find("[FILE_EXPORT]"))
