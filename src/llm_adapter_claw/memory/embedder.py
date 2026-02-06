"""Embedding generator for text vectorization."""

import hashlib
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


class HashEmbedder:
    """Simple hash-based embedder (fallback when ML libs unavailable).

    Uses multiple hash algorithms to create a deterministic
    but non-semantic embedding. Good for exact/near-exact matching.
    """

    def __init__(self, dim: int = 384) -> None:
        """Initialize hash embedder.

        Args:
            dim: Embedding dimension (default 384 for compatibility)
        """
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        """Generate hash-based embedding.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        # Normalize text
        normalized = text.lower().strip()

        # Use multiple hash algorithms for better distribution
        md5_hash = hashlib.md5(normalized.encode()).digest()
        sha256_hash = hashlib.sha256(normalized.encode()).digest()

        # Combine hashes to fill dimension
        combined = md5_hash + sha256_hash

        # Expand or truncate to target dimension
        vector = []
        for i in range(self.dim):
            byte_val = combined[i % len(combined)]
            # Normalize to [-1, 1]
            vector.append((byte_val / 127.5) - 1.0)

        # L2 normalize
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for batch.

        Args:
            texts: Input texts

        Returns:
            List of embedding vectors
        """
        return [self.embed(t) for t in texts]


class SentenceTransformerEmbedder:
    """Sentence transformer embedder (requires sentence-transformers)."""

    def __init__(
        self,
        model: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu",
    ) -> None:
        """Initialize sentence transformer embedder.

        Args:
            model: Model name
            device: Device (cpu/cuda)
        """
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(model, device=device)
            self.dim = self.model.get_sentence_embedding_dimension()
            logger.info("embedder.loaded", model=model, dim=self.dim)
        except ImportError as e:
            raise ImportError(
                f"sentence-transformers not installed: {e}. "
                "Install with: pip install sentence-transformers"
            )

    def embed(self, text: str) -> list[float]:
        """Generate embedding using transformer.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate batch embeddings.

        Args:
            texts: Input texts

        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]


class NoOpEmbedder:
    """No-op embedder for testing."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        """Return zero vector."""
        logger.debug("embedder.noop", text_len=len(text))
        return [0.0] * self.dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return zero vectors."""
        return [[0.0] * self.dim for _ in texts]


def create_embedder(
    model: str = "hash",
    device: str = "cpu",
    dim: int = 384,
) -> Embedder:
    """Factory for embedder.

    Args:
        model: Model name ("hash", "transformer", "noop", or specific model)
        device: Device for computation
        dim: Embedding dimension (for hash/noop)

    Returns:
        Embedder instance
    """
    if model == "noop":
        return NoOpEmbedder(dim)

    if model == "hash":
        return HashEmbedder(dim)

    if model == "transformer":
        try:
            return SentenceTransformerEmbedder(
                "BAAI/bge-small-zh-v1.5", device
            )
        except ImportError:
            logger.warning(
                "embedder.fallback_to_hash",
                reason="sentence-transformers not installed",
            )
            return HashEmbedder(dim)

    # Try to load as sentence-transformer model
    try:
        return SentenceTransformerEmbedder(model, device)
    except ImportError:
        logger.warning(
            "embedder.fallback_to_hash",
            model=model,
            reason="sentence-transformers not installed",
        )
        return HashEmbedder(dim)
