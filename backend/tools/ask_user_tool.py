"""Ask User Tool - Human-in-the-loop for agent to request user input"""
from typing import List, Optional
from langchain_core.tools import tool
from langgraph.types import interrupt


@tool
def ask_user(description: Optional[str], questions: List[str], default_response: Optional[str] = None) -> str:
    """Pause execution and request information from the user.

    Args:
        description: Optional context explaining why these questions are being asked.
                     Displayed as header text above the questions.
        questions: List of questions to present to the user. Each question should be a 
                   separate item - do NOT combine multiple questions into one string.
        default_response: Optional default text pre-filled in a general text input field.
                          Use this to suggest a reasonable default the user can accept or edit.
    
    Returns:
        The user's text response
    """
    response = interrupt({"description": description, "questions": questions, "default_response": default_response})
    return response
