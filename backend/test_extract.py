import json
from typing import Optional, Dict
from langgraph.types import Command
from langchain_core.messages import ToolMessage

def _extract_file_export_data(content: str) -> Optional[Dict[str, str]]:
    """Extract file export data from tool result content"""
    # Simple string extraction instead of regex
    start_tag = '[FILE_EXPORT]'
    end_tag = '[/FILE_EXPORT]'

    start_idx = content.find(start_tag)
    if start_idx == -1:
        return None

    end_idx = content.find(end_tag)
    if end_idx == -1:
        return None

    # Extract JSON content between tags
    json_start = start_idx + len(start_tag)
    file_json = content[json_start:end_idx].strip()

    if not file_json:
        return None

    try:
        file_data = json.loads(file_json)

        if file_data.get('filepath') and file_data.get('filename'):
            return {
                'filepath': file_data['filepath'],
                'filename': file_data['filename'],
                'file_type': file_data.get('type', 'unknown'),
                'description': file_data.get('description')
            }
    except Exception as e:
        print("JSON parse error:", e)
        print("Failed to parse:", file_json)
    return None

success_msg = "test [FILE_EXPORT]{\"filepath\": \"a\", \"filename\": \"b\", \"type\": \"excel\"}[/FILE_EXPORT]"
cmd = Command(update={"messages": [ToolMessage(content=success_msg, tool_call_id="123")]})

# Simulate parsing
result_content = str(cmd)
print("String content:")
print(result_content)

print("\nExtracted Data:")
print(_extract_file_export_data(result_content))

