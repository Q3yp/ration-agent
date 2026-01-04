"""Ask User Tool - Human-in-the-loop for agent to request user input"""
from typing import List, Optional
from langchain_core.tools import tool
from langgraph.types import interrupt


@tool
def ask_user(description: Optional[str], questions: List[str]) -> str:
    """Pause execution and request information from the user.

    Args:
        description: Optional context explaining why these questions are being asked.
                     Displayed as header text above the questions.
        questions: List of questions to present to the user. Each question should be a 
                   separate item - do NOT combine multiple questions into one string.
    
    Returns:
        The user's text response
    """
    response = interrupt({"description": description, "questions": questions})
    return response
