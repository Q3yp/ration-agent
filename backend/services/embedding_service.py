"""
Embedding service for semantic feed search.
Uses OpenAI text-embedding-3-small via configurable endpoint.
"""

import os
import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Embedding service for semantic feed search.
    
    Pre-computed embeddings are loaded from feed_embeddings.json.
    Runtime queries are embedded via configured API endpoint.
    """
    
    _instance: Optional['EmbeddingService'] = None
    _embeddings: Optional[Dict[str, List[float]]] = None
    _feed_texts: Optional[Dict[str, str]] = None
    
    def __init__(self):
        self.model = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
        self.endpoint = os.getenv("EMBEDDING_ENDPOINT", "https://openrouter.ai/api/v1")
        self.api_key = os.getenv("EMBEDDING_API_KEY")
        self.dimension = 1024  # text-embedding-v4 (DashScope) dimension
        
    @classmethod
    def get_instance(cls) -> 'EmbeddingService':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_embeddings()
        return cls._instance
    
    def _load_embeddings(self):
        """Load pre-computed embeddings from JSON file."""
        embeddings_path = Path(__file__).parent.parent / "scripts" / "feed_embeddings.json"
        
        if not embeddings_path.exists():
            logger.warning(f"Feed embeddings not found at {embeddings_path}. Semantic search disabled.")
            self._embeddings = {}
            self._feed_texts = {}
            return
            
        try:
            with open(embeddings_path, 'r') as f:
                data = json.load(f)
            
            self._embeddings = data.get("embeddings", {})
            self._feed_texts = data.get("feed_texts", {})
            logger.info(f"Loaded {len(self._embeddings)} feed embeddings from {embeddings_path}")
        except Exception as e:
            logger.error(f"Error loading feed embeddings: {e}")
            self._embeddings = {}
            self._feed_texts = {}
    
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text using configured API endpoint."""
        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY not set")
        
        url = f"{self.endpoint}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": text
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
        return data["data"][0]["embedding"]
    
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    async def search(
        self, 
        query: str, 
        feedbase_name: str = "default_dairy_cow",
        limit: int = 10
    ) -> List[tuple]:
        """
        Search for feeds semantically similar to query.
        
        Args:
            query: Search query text
            feedbase_name: Name of feedbase (currently only default_dairy_cow has embeddings)
            limit: Maximum number of results to return
            
        Returns:
            List of (feed_name, similarity_score) tuples, sorted by similarity descending
        """
        if not self._embeddings:
            logger.warning("No embeddings loaded, semantic search unavailable")
            return []
        
        # Embed the query
        try:
            query_embedding = await self.embed(query)
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            return []
        
        # Compute similarity against all feed embeddings
        similarities = []
        for feed_name, feed_embedding in self._embeddings.items():
            similarity = self.cosine_similarity(query_embedding, feed_embedding)
            similarities.append((feed_name, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:limit]
    
    def has_embeddings(self) -> bool:
        """Check if embeddings are loaded."""
        return bool(self._embeddings)
    
    def get_feed_text(self, feed_name: str) -> Optional[str]:
        """Get the text that was embedded for a feed."""
        if self._feed_texts:
            return self._feed_texts.get(feed_name)
        return None


def get_embedding_service() -> EmbeddingService:
    """Get the embedding service singleton."""
    return EmbeddingService.get_instance()
