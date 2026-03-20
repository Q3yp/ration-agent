import json
from langgraph.types import Command
from langchain_core.messages import ToolMessage

success_msg = 'test [FILE_EXPORT]{"filepath": "a", "filename": "b\'s file", "type": "excel"}[/FILE_EXPORT]'
cmd = Command(update={"messages": [ToolMessage(content=success_msg, tool_call_id="123")]})

result_content = str(cmd)
print("String content:", result_content)

start_tag = '[FILE_EXPORT]'
end_tag = '[/FILE_EXPORT]'

start_idx = result_content.find(start_tag)
end_idx = result_content.find(end_tag)

json_start = start_idx + len(start_tag)
file_json = result_content[json_start:end_idx].strip()
print("Extracted JSON:", file_json)

try:
    print(json.loads(file_json))
except Exception as e:
    print("JSON Error:", e)
