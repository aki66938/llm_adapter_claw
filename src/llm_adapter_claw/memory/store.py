"""Memory store abstraction for vector database."""

from typing import Protocol

from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class MemoryStore(Protocol):
    """Protocol for memory storage backends."""
    
    async def add(self, text: str, metadata: dict | None = None) -> str:
        """Add memory to store.
        
        Args:
            text: Memory content
            metadata: Optional metadata
            
        Returns:
            Memory ID
        """
        ...
    
    async def search(self, query: str, top_k: int = 3) -> list[dict]:
        """Search memories by similarity.
        
        Args:
            query: Search query
            top_k: Number of results
            
        Returns:
            List of matching memories
        """
        ...
    
    async def delete(self, memory_id: str) -> bool:
        """Delete memory by ID.
        
        Args:
            memory_id: Memory identifier
            
        Returns:
            True if deleted
        """
        ...


class NoOpMemoryStore:
    """No-op memory store for Phase 1-2 (placeholder)."""
    
    async def add(self, text: str, metadata: dict | None = None) -> str:
        """No-op add."""
        logger.debug("memory.add_noop", text_len=len(text))
        return "noop_id"
    
    async def search(self, query: str, top_k: int = 3) -> list[dict]:
        """No-op search."""
        logger.debug("memory.search_noop", query=query)
        return []
    
    async def delete(self, memory_id: str) -> bool:
        """No-op delete."""
        logger.debug("memory.delete_noop", id=memory_id)
        return True


def create_store(backend: str = "noop", **kwargs) -> MemoryStore:
    """Factory for memory store.
    
    Args:
        backend: Storage backend ("noop", "chromadb", "sqlite-vss")
        **kwargs: Backend-specific options
        
    Returns:
        Memory store instance
    """
    if backend == "noop":
        return NoOpMemoryStore()
    # TODO: Implement ChromaDB and SQLite-VSS backends in Phase 3
    raise ValueError(f"Unknown backend: {backend}")
