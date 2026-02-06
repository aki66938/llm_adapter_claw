"""Memory store abstraction for vector database."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryEntry:
    """A memory entry."""

    id: str
    text: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] | None = None
    timestamp: float = 0.0


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

    async def search(
        self, query_embedding: list[float], top_k: int = 3
    ) -> list[dict]:
        """Search memories by embedding similarity.

        Args:
            query_embedding: Query vector
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

    async def clear(self) -> None:
        """Clear all memories."""
        ...


class SQLiteVSSStore:
    """SQLite-VSS vector store backend.

    Uses sqlite-vss extension for vector similarity search.
    Falls back to simple cosine similarity if vss unavailable.
    """

    def __init__(
        self,
        db_path: str = "./memory_store/vss.db",
        embedding_dim: int = 384,
    ) -> None:
        """Initialize SQLite-VSS store.

        Args:
            db_path: Database file path
            embedding_dim: Embedding dimension
        """
        self.db_path = Path(db_path)
        self.embedding_dim = embedding_dim
        self._vss_available = False
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import sqlite_vss

            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.enable_load_extension(True)
            sqlite_vss.load(self.conn)
            self._vss_available = True
            logger.info("store.vss_loaded", path=str(self.db_path))
        except (ImportError, Exception) as e:
            logger.warning(
                "store.vss_unavailable",
                error=str(e),
                fallback="cosine_similarity",
            )
            self.conn = sqlite3.connect(str(self.db_path))
            self._vss_available = False

        self._create_tables()

    def _create_tables(self) -> None:
        """Create database tables."""
        cursor = self.conn.cursor()

        # Main memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                metadata TEXT,
                timestamp REAL DEFAULT (unixepoch())
            )
        """)

        # VSS virtual table (only if vss available)
        if self._vss_available:
            try:
                cursor.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS vss_memories USING vss0(
                        embedding({self.embedding_dim})
                    )
                """)
            except Exception as e:
                logger.warning("store.vss_table_failed", error=str(e))
                self._vss_available = False

        self.conn.commit()

    async def add(
        self,
        text: str,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> str:
        """Add memory with embedding.

        Args:
            text: Memory content
            embedding: Vector embedding
            metadata: Optional metadata

        Returns:
            Memory ID
        """
        import time
        import uuid

        memory_id = str(uuid.uuid4())
        embedding_json = json.dumps(embedding)
        metadata_json = json.dumps(metadata) if metadata else None

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (id, text, embedding, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (memory_id, text, embedding_json, metadata_json, time.time()),
        )

        # Add to VSS index if available
        if self._vss_available:
            try:
                cursor.execute(
                    "INSERT INTO vss_memories (rowid, embedding) VALUES (?, ?)",
                    (cursor.lastrowid, embedding_json),
                )
            except Exception as e:
                logger.warning("store.vss_index_failed", error=str(e))

        self.conn.commit()
        logger.debug("store.added", id=memory_id, text_len=len(text))
        return memory_id

    async def search(
        self, query_embedding: list[float], top_k: int = 3
    ) -> list[dict]:
        """Search by embedding similarity.

        Args:
            query_embedding: Query vector
            top_k: Number of results

        Returns:
            List of matching memories
        """
        if self._vss_available:
            return await self._search_vss(query_embedding, top_k)
        return await self._search_cosine(query_embedding, top_k)

    async def _search_vss(
        self, query_embedding: list[float], top_k: int
    ) -> list[dict]:
        """Search using VSS index."""
        import json

        embedding_json = json.dumps(query_embedding)
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT m.id, m.text, m.metadata, m.timestamp, v.distance
                FROM vss_memories v
                JOIN memories m ON m.rowid = v.rowid
                WHERE vss_search(v.embedding, ?)
                ORDER BY v.distance
                LIMIT ?
                """,
                (embedding_json, top_k),
            )
        except Exception as e:
            logger.warning("store.vss_search_failed", error=str(e))
            return await self._search_cosine(query_embedding, top_k)

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "text": row[1],
                "metadata": json.loads(row[2]) if row[2] else None,
                "timestamp": row[3],
                "distance": row[4],
            })

        return results

    async def _search_cosine(
        self, query_embedding: list[float], top_k: int
    ) -> list[dict]:
        """Search using cosine similarity (fallback)."""
        import json
        import math

        cursor = self.conn.cursor()
        cursor.execute("SELECT id, text, embedding, metadata, timestamp FROM memories")

        # Compute cosine similarity for all entries
        scored = []
        query_norm = math.sqrt(sum(x * x for x in query_embedding))

        for row in cursor.fetchall():
            embedding = json.loads(row[2])
            # Cosine similarity
            dot = sum(a * b for a, b in zip(query_embedding, embedding))
            norm = math.sqrt(sum(x * x for x in embedding))
            if norm > 0 and query_norm > 0:
                similarity = dot / (query_norm * norm)
            else:
                similarity = 0

            scored.append((similarity, row))

        # Sort by similarity (descending)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return top_k
        results = []
        for similarity, row in scored[:top_k]:
            results.append({
                "id": row[0],
                "text": row[1],
                "metadata": json.loads(row[3]) if row[3] else None,
                "timestamp": row[4],
                "similarity": similarity,
            })

        return results

    async def delete(self, memory_id: str) -> bool:
        """Delete memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        deleted = cursor.rowcount > 0
        self.conn.commit()
        logger.debug("store.deleted", id=memory_id, success=deleted)
        return deleted

    async def clear(self) -> None:
        """Clear all memories."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memories")
        if self._vss_available:
            try:
                cursor.execute("DELETE FROM vss_memories")
            except Exception:
                pass
        self.conn.commit()
        logger.info("store.cleared")

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()


class InMemoryStore:
    """In-memory store for testing (no persistence)."""

    def __init__(self) -> None:
        """Initialize in-memory store."""
        self._memories: dict[str, MemoryEntry] = {}

    async def add(
        self,
        text: str,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> str:
        """Add memory."""
        import time
        import uuid

        memory_id = str(uuid.uuid4())
        self._memories[memory_id] = MemoryEntry(
            id=memory_id,
            text=text,
            embedding=embedding,
            metadata=metadata,
            timestamp=time.time(),
        )
        return memory_id

    async def search(
        self, query_embedding: list[float], top_k: int = 3
    ) -> list[dict]:
        """Search by cosine similarity."""
        import math

        if not self._memories:
            return []

        query_norm = math.sqrt(sum(x * x for x in query_embedding))
        scored = []

        for entry in self._memories.values():
            if entry.embedding:
                dot = sum(a * b for a, b in zip(query_embedding, entry.embedding))
                norm = math.sqrt(sum(x * x for x in entry.embedding))
                if norm > 0 and query_norm > 0:
                    similarity = dot / (query_norm * norm)
                else:
                    similarity = 0
                scored.append((similarity, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "id": entry.id,
                "text": entry.text,
                "metadata": entry.metadata,
                "timestamp": entry.timestamp,
                "similarity": similarity,
            }
            for similarity, entry in scored[:top_k]
        ]

    async def delete(self, memory_id: str) -> bool:
        """Delete memory."""
        if memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False

    async def clear(self) -> None:
        """Clear all memories."""
        self._memories.clear()


class NoOpMemoryStore:
    """No-op memory store for testing."""

    async def add(
        self,
        text: str,
        embedding: list[float] | None = None,
        metadata: dict | None = None,
    ) -> str:
        """No-op add."""
        import uuid

        return str(uuid.uuid4())

    async def search(
        self, query_embedding: list[float], top_k: int = 3
    ) -> list[dict]:
        """No-op search."""
        return []

    async def delete(self, memory_id: str) -> bool:
        """No-op delete."""
        return True

    async def clear(self) -> None:
        """No-op clear."""
        pass


def create_store(
    backend: str = "sqlite-vss",
    db_path: str = "./memory_store/vss.db",
    embedding_dim: int = 384,
) -> MemoryStore:
    """Factory for memory store.

    Args:
        backend: Storage backend ("sqlite-vss", "memory", "noop")
        db_path: Database path for SQLite backend
        embedding_dim: Embedding dimension

    Returns:
        Memory store instance
    """
    if backend == "noop":
        return NoOpMemoryStore()

    if backend == "memory":
        return InMemoryStore()

    if backend == "sqlite-vss":
        return SQLiteVSSStore(db_path, embedding_dim)

    raise ValueError(f"Unknown backend: {backend}")
