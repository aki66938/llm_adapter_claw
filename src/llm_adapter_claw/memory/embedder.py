"""Embedding generator for text vectorization."""

from typing import Protocol

from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class Embedder(Protocol):
    """Protocol for text embedding."""
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding for text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector
        """
        ...
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: Input texts
            
        Returns:
            List of embedding vectors
        """
        ...


class NoOpEmbedder:
    """No-op embedder for Phase 1-2 (placeholder)."""
    
    def embed(self, text: str) -> list[float]:
        """Return zero vector."""
        logger.debug("embedder.noop", text_len=len(text))
        return [0.0] * 384  # Standard embedding size
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return zero vectors."""
        return [[0.0] * 384 for _ in texts]


def create_embedder(model: str = "noop", device: str = "cpu") -> Embedder:
    """Factory for embedder.
    
    Args:
        model: Model name or "noop"
        device: Device for computation
        
    Returns:
        Embedder instance
    """
    if model == "noop":
        return NoOpEmbedder()
    # TODO: Implement sentence-transformers in Phase 3
    raise ValueError(f"Unknown embedder: {model}")
