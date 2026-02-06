"""Memory retriever for semantic search."""

from llm_adapter_claw.memory.embedder import Embedder, create_embedder
from llm_adapter_claw.memory.store import MemoryStore, create_store
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class MemoryRetriever:
    """Retrieves relevant memories for context augmentation."""

    def __init__(
        self,
        store: MemoryStore,
        embedder: Embedder,
        default_top_k: int = 3,
        similarity_threshold: float = 0.5,
    ) -> None:
        """Initialize retriever.

        Args:
            store: Memory storage backend
            embedder: Text embedder
            default_top_k: Default number of results
            similarity_threshold: Minimum similarity score (0-1)
        """
        self.store = store
        self.embedder = embedder
        self.default_top_k = default_top_k
        self.similarity_threshold = similarity_threshold

    async def add_memory(
        self, text: str, metadata: dict | None = None
    ) -> str:
        """Add a memory to the store.

        Args:
            text: Memory content
            metadata: Optional metadata

        Returns:
            Memory ID
        """
        embedding = self.embedder.embed(text)
        memory_id = await self.store.add(text, embedding, metadata)
        logger.debug("retriever.added", id=memory_id, text_len=len(text))
        return memory_id

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        include_metadata: bool = False,
    ) -> list[str] | list[dict]:
        """Retrieve relevant memories.

        Args:
            query: Search query
            top_k: Number of results (uses default if None)
            include_metadata: If True, return full dicts instead of just text

        Returns:
            List of memory texts or full memory dicts
        """
        k = top_k or self.default_top_k

        # Generate query embedding
        query_embedding = self.embedder.embed(query)

        # Search store
        results = await self.store.search(query_embedding, k)

        # Filter by threshold
        filtered = [
            r for r in results
            if r.get("similarity", 1.0) >= self.similarity_threshold
            or r.get("distance", 0) <= (1 - self.similarity_threshold)
        ]

        logger.info(
            "retriever.search",
            query=query[:50],
            raw_results=len(results),
            filtered_results=len(filtered),
        )

        if include_metadata:
            return filtered
        return [r.get("text", "") for r in filtered]

    async def retrieve_for_context(
        self,
        query: str,
        top_k: int | None = None,
        format_template: str = "Relevant context from memory: {text}",
    ) -> str:
        """Retrieve memories formatted for injection into context.

        Args:
            query: Search query
            top_k: Number of results
            format_template: Template for formatting each memory

        Returns:
            Formatted context string (empty if no results)
        """
        memories = await self.retrieve(query, top_k, include_metadata=False)

        if not memories:
            return ""

        formatted = [format_template.format(text=m) for m in memories]
        return "\n".join(formatted)

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        return await self.store.delete(memory_id)

    async def clear(self) -> None:
        """Clear all memories."""
        await self.store.clear()
        logger.info("retriever.cleared")


def create_retriever(
    store: MemoryStore | None = None,
    embedder: Embedder | None = None,
    store_backend: str = "sqlite-vss",
    embedder_model: str = "hash",
    top_k: int = 3,
    db_path: str = "./memory_store/vss.db",
) -> MemoryRetriever:
    """Factory for memory retriever.

    Args:
        store: Memory store (creates default if None)
        embedder: Text embedder (creates default if None)
        store_backend: Store backend type
        embedder_model: Embedder model type
        top_k: Default top_k
        db_path: Database path for SQLite store

    Returns:
        Configured retriever
    """
    if store is None:
        store = create_store(backend=store_backend, db_path=db_path)

    if embedder is None:
        embedder = create_embedder(model=embedder_model)

    return MemoryRetriever(store, embedder, top_k)
