"""
Chat History Service for managing conversation history across sessions
"""
from typing import List, Dict, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import os
import psycopg
from langchain_postgres import PostgresChatMessageHistory


class ChatHistoryService:
    """Service for managing chat history with PostgreSQL persistence"""
    
    def __init__(self):
        # Create direct connection to PostgreSQL
        self.connection_string = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    def add_user_message(self, session_id: str, content: str):
        """Add a user message to session history"""
        message = HumanMessage(content=content)
        with psycopg.connect(self.connection_string) as conn:
            chat_history = PostgresChatMessageHistory(
                table_name="chat_history",
                session_id=session_id,
                sync_connection=conn
            )
            chat_history.add_messages([message])
    
    def add_ai_message(self, session_id: str, content: str):
        """Add an AI message to session history"""
        message = AIMessage(content=content)
        with psycopg.connect(self.connection_string) as conn:
            chat_history = PostgresChatMessageHistory(
                table_name="chat_history",
                session_id=session_id,
                sync_connection=conn
            )
            chat_history.add_messages([message])
    
    def add_system_message(self, session_id: str, content: str):
        """Add a system message to session history"""
        message = SystemMessage(content=content)
        with psycopg.connect(self.connection_string) as conn:
            chat_history = PostgresChatMessageHistory(
                table_name="chat_history",
                session_id=session_id,
                sync_connection=conn
            )
            chat_history.add_messages([message])
    
    def add_messages(self, session_id: str, messages: List[BaseMessage]):
        """Add multiple messages to session history"""
        with psycopg.connect(self.connection_string) as conn:
            chat_history = PostgresChatMessageHistory(
                table_name="chat_history",
                session_id=session_id,
                sync_connection=conn
            )
            chat_history.add_messages(messages)
    
    def get_session_history(self, session_id: str) -> List[BaseMessage]:
        """Get all messages for a session"""
        with psycopg.connect(self.connection_string) as conn:
            chat_history = PostgresChatMessageHistory(
                table_name="chat_history",
                session_id=session_id,
                sync_connection=conn
            )
            return chat_history.messages
    
    def get_recent_messages(self, session_id: str, limit: int = 20) -> List[BaseMessage]:
        """Get recent messages for a session (last N messages)"""
        messages = self.get_session_history(session_id)
        return messages[-limit:] if len(messages) > limit else messages
    
    def clear_session_history(self, session_id: str):
        """Clear all messages for a session"""
        with psycopg.connect(self.connection_string) as conn:
            chat_history = PostgresChatMessageHistory(
                table_name="chat_history",
                session_id=session_id,
                sync_connection=conn
            )
            chat_history.clear()
    
    def get_session_summary(self, session_id: str) -> Dict:
        """Get summary statistics for a session"""
        messages = self.get_session_history(session_id)
        
        human_count = sum(1 for msg in messages if isinstance(msg, HumanMessage))
        ai_count = sum(1 for msg in messages if isinstance(msg, AIMessage))
        system_count = sum(1 for msg in messages if isinstance(msg, SystemMessage))
        
        return {
            "session_id": session_id,
            "total_messages": len(messages),
            "human_messages": human_count,
            "ai_messages": ai_count,
            "system_messages": system_count,
            "has_history": len(messages) > 0
        }
    
    def format_history_for_context(self, session_id: str, max_messages: int = 10) -> str:
        """Format recent message history for context in prompts"""
        messages = self.get_recent_messages(session_id, max_messages)
        
        if not messages:
            return "No previous conversation history."
        
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted_messages.append(f"Human: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_messages.append(f"Assistant: {msg.content}")
            elif isinstance(msg, SystemMessage):
                formatted_messages.append(f"System: {msg.content}")
        
        return "\n".join(formatted_messages)


# Global chat history service instance
chat_history_service = ChatHistoryService()