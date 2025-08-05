"""
RAGFlow integration for LangGraph agents.
Provides tools for document ingestion, search, and retrieval using RAGFlow.
"""

import json
import os
import uuid
import asyncio
import logging
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
from langchain_core.tools import tool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class RAGFlowClient:
    """Client for interacting with RAGFlow API"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")).rstrip('/')
        self.api_key = api_key or os.getenv("RAGFLOW_API_KEY")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[Any, Any]:
        """Make HTTP request to RAGFlow API"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"RAGFlow API request failed: {e}")
            raise Exception(f"RAGFlow API request failed: {e}")
    
    def create_dataset(self, name: str, description: str = "", embedding_model: str = "BAAI/bge-small-en-v1.5") -> Dict[Any, Any]:
        """Create a new RAGFlow dataset (knowledge base)"""
        payload = {
            "name": name,
            "description": description,
            "language": "English",
            "embedding_model": embedding_model,
            "permission": "me",
            "document_count": 0,
            "chunk_count": 0,
            "parse_method": "naive",
            "parser_config": {
                "chunk_token_count": 128,
                "layout_recognize": True,
                "delimiter": "\n!?;。；！？",
                "task_page_size": 12
            }
        }
        return self._make_request("POST", "/api/v1/datasets", json=payload)
    
    def list_datasets(self) -> List[Dict[Any, Any]]:
        """List all datasets"""
        response = self._make_request("GET", "/api/v1/datasets")
        return response.get("data", [])
    
    def upload_document(self, dataset_id: str, file_path: str) -> Dict[Any, Any]:
        """Upload a document to a dataset"""
        with open(file_path, 'rb') as f:
            files = {"file": (Path(file_path).name, f, "application/octet-stream")}
            data = {"dataset_id": dataset_id}
            return self._make_request("POST", "/v1/documents", files=files, data=data)
    
    def parse_documents(self, dataset_id: str, document_ids: List[str]) -> Dict[Any, Any]:
        """Parse uploaded documents in a dataset"""
        payload = {
            "dataset_id": dataset_id,
            "document_ids": document_ids
        }
        return self._make_request("POST", "/v1/documents/parse", json=payload)
    
    def search_chunks(self, dataset_id: str, query: str, limit: int = 6, similarity_threshold: float = 0.2) -> Dict[Any, Any]:
        """Search for relevant chunks in a dataset"""
        payload = {
            "dataset_ids": [dataset_id],
            "question": query,
            "page_size": limit,
            "similarity_threshold": similarity_threshold,
            "page": 1
        }
        return self._make_request("POST", "/api/v1/retrieval", json=payload)
    
    def create_chat_assistant(self, name: str, dataset_ids: List[str], llm_model: str = "gpt-3.5-turbo") -> Dict[Any, Any]:
        """Create a chat assistant with specified datasets"""
        payload = {
            "name": name,
            "description": f"RAG assistant for datasets: {', '.join(dataset_ids)}",
            "language": "English",
            "dataset_ids": dataset_ids,
            "llm": {
                "model_name": llm_model,
                "temperature": 0.1,
                "top_p": 0.3,
                "presence_penalty": 0.4,
                "frequency_penalty": 0.7,
                "max_tokens": 512
            },
            "prompt": {
                "similarity_threshold": 0.2,
                "keywords_similarity_weight": 0.3,
                "top_n": 6,
                "variables": [
                    {"key": "knowledge", "optional": False}
                ],
                "rerank_model": "",
                "empty_response": "Sorry, I don't know.",
                "opener": "Hi! I'm your assistant, what can I help you with?",
                "show_quote": True,
                "prompt": "You are an intelligent assistant. Please summarize the content of the knowledge base to answer the question. Please list the data in the knowledge base and answer in detail. When all knowledge base content is not related to the question, ONLY REPLY 'Sorry, I don't know.'\n\n#Knowledge Base:\n{knowledge}\n\n#Question:\n{question}"
            }
        }
        return self._make_request("POST", "/v1/chat/assistants", json=payload)
    
    def create_chat_session(self, assistant_id: str) -> Dict[Any, Any]:
        """Create a new chat session with an assistant"""
        payload = {"assistant_id": assistant_id}
        return self._make_request("POST", "/v1/chat/sessions", json=payload)
    
    def chat_with_assistant(self, session_id: str, message: str, stream: bool = False) -> Dict[Any, Any]:
        """Send a message to the chat assistant"""
        payload = {
            "session_id": session_id,
            "message": message,
            "stream": stream
        }
        return self._make_request("POST", "/v1/chat/completions", json=payload)


# Global RAGFlow client instance
_ragflow_client = None

def get_ragflow_client() -> RAGFlowClient:
    """Get or create RAGFlow client instance"""
    global _ragflow_client
    if _ragflow_client is None:
        _ragflow_client = RAGFlowClient()
    return _ragflow_client


@tool
async def search_knowledge_base(query: str, limit: int = 6) -> str:
    """Search for relevant information in the ration formulation knowledge base using semantic similarity

    Args:
        query: The search query or question about animal nutrition, feed formulation, or dairy cattle requirements
        limit: Maximum number of results to return (default: 6)
    """
    try:
        client = get_ragflow_client()
        dataset_id = os.getenv("RAGFLOW_DATASET_ID")

        if not dataset_id:
            return "Error: RAGFlow dataset ID not configured. Please set RAGFLOW_DATASET_ID in environment variables."

        result = client.search_chunks(dataset_id, query, limit)

        chunks = result.get("data", {}).get("chunks", [])
        if not chunks:
            return f"🔍 No relevant information found for query: '{query}'\nTry adjusting your search terms or using different keywords."

        search_results = [f"🔍 Knowledge Base Search Results for: '{query}'"]
        search_results.append(f"Found {len(chunks)} relevant chunks:")
        search_results.append("")

        for i, chunk in enumerate(chunks, 1):
            similarity = chunk.get("similarity", 0)
            content = chunk.get("content_with_weight", chunk.get("content", "No content"))
            doc_name = chunk.get("document_name", "Unknown document")

            search_results.append(f"{i}. **{doc_name}** (Similarity: {similarity:.3f})")
            search_results.append(f"   {content[:300]}{'...' if len(content) > 300 else ''}")
            search_results.append("")

        return "\n".join(search_results)

    except Exception as e:
        logger.error(f"Failed to search knowledge base: {e}")
        return f"❌ Error searching knowledge base: {str(e)}"


def get_ragflow_tools() -> List:
    """Get RAGFlow retrieval tools for LangGraph agents"""
    return [
        search_knowledge_base
    ]


def create_ragflow_tools_for_session(session_id: str) -> List:
    """Create RAGFlow retrieval tools for a specific session"""
    # Return only the knowledge base search tool
    return get_ragflow_tools()