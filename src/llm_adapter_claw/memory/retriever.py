"""Memory retriever for semantic search."""

from llm_adapter_claw.memory.store import MemoryStore
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class MemoryRetriever:
    """Retrieves relevant memories for context augmentation.
    
    Phase 3 implementation: semantic memory retrieval
    """
    
    def __init__(self, store: MemoryStore, default_top_k: int = 3) -> None:
        """Initialize retriever.
        
        Args:
            store: Memory storage backend
            default_top_k: Default number of results
        """
        self.store = store
        self.default_top_k = default_top_k
    
    async def retrieve(self, query: str, top_k: int | None = None) -> list[str]:
        """Retrieve relevant memory texts.
        
        Args:
            query: Search query
            top_k: Number of results (uses default if None)
            
        Returns:
            List of memory text contents
        """
        k = top_k or self.default_top_k
        results = await self.store.search(query, top_k=k)
        
        logger.info("memory.retrieved", query=query, count=len(results))
        return [r.get("text", "") for r in results]


def create_retriever(store: MemoryStore | None = None, top_k: int = 3):
    """Factory for memory retriever.
    
    Args:
        store: Memory store (creates noop if None)
        top_k: Default top_k
        
    Returns:
        Configured retriever
    """
    if store is None:
        from llm_adapter_claw.memory.store import create_store
        store = create_store()
    return MemoryRetriever(store, top_k)
