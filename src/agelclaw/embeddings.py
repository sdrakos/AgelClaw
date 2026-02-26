"""
Embedding Store — Semantic Search via sqlite-vec + OpenAI
=========================================================
Provides vector similarity search across conversations, tasks, and learnings.

Uses:
- sqlite-vec: native SQLite vector extension for storing/querying embeddings
- OpenAI text-embedding-3-small: 1536-dimension embeddings

Graceful degradation: if sqlite-vec or openai key is unavailable, all methods
return empty results without raising errors.
"""

import hashlib
import logging
import sqlite3
import struct
from pathlib import Path
from typing import Optional

log = logging.getLogger("embeddings")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
BATCH_SIZE = 64  # OpenAI allows up to ~8k tokens per batch


def _serialize_f32(vec: list[float]) -> bytes:
    """Serialize a list of floats into little-endian binary for sqlite-vec."""
    return struct.pack(f"<{len(vec)}f", *vec)


class EmbeddingStore:
    def __init__(self, db_path: Path, openai_api_key: str = ""):
        self.db_path = db_path
        self.openai_api_key = openai_api_key
        self._openai_client = None
        self._vec_available = False

        # Try to load sqlite-vec
        try:
            import sqlite_vec
            self._sqlite_vec = sqlite_vec
            self._vec_available = True
        except ImportError:
            log.warning("sqlite-vec not installed — semantic search disabled")
            return

        # Verify OpenAI key
        if not openai_api_key:
            log.warning("No OpenAI API key — semantic search disabled")
            self._vec_available = False
            return

        self._init_vec_tables()

    @property
    def available(self) -> bool:
        return self._vec_available

    def _get_conn(self) -> sqlite3.Connection:
        """Get a connection with sqlite-vec loaded."""
        conn = sqlite3.connect(str(self.db_path))
        conn.enable_load_extension(True)
        self._sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_vec_tables(self):
        """Create sqlite-vec virtual tables and metadata tracking table."""
        conn = self._get_conn()
        try:
            conn.executescript(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_conversations
                    USING vec0(embedding float[{EMBEDDING_DIM}]);

                CREATE VIRTUAL TABLE IF NOT EXISTS vec_tasks
                    USING vec0(embedding float[{EMBEDDING_DIM}]);

                CREATE VIRTUAL TABLE IF NOT EXISTS vec_learnings
                    USING vec0(embedding float[{EMBEDDING_DIM}]);

                CREATE TABLE IF NOT EXISTS embeddings_meta (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    row_id INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(table_name, row_id)
                );

                CREATE INDEX IF NOT EXISTS idx_emb_meta_table
                    ON embeddings_meta(table_name);
            """)
            conn.commit()
        except Exception as e:
            log.error(f"Failed to init vec tables: {e}")
            self._vec_available = False
        finally:
            conn.close()

    def _get_openai_client(self):
        """Lazy-init OpenAI client."""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=self.openai_api_key)
        return self._openai_client

    def _get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding for a single text string."""
        try:
            client = self._get_openai_client()
            # Truncate to ~8000 tokens (~32000 chars) to stay within limits
            if len(text) > 30000:
                text = text[:30000]
            resp = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
            return resp.data[0].embedding
        except Exception as e:
            log.error(f"OpenAI embedding error: {e}")
            return None

    def _get_embeddings_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        """Get embeddings for a batch of texts."""
        try:
            client = self._get_openai_client()
            # Truncate each text
            truncated = [t[:30000] if len(t) > 30000 else t for t in texts]
            resp = client.embeddings.create(input=truncated, model=EMBEDDING_MODEL)
            return [item.embedding for item in resp.data]
        except Exception as e:
            log.error(f"OpenAI batch embedding error: {e}")
            return [None] * len(texts)

    def _content_hash(self, text: str) -> str:
        """SHA256 hash of content to detect changes."""
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]

    def _is_already_embedded(self, conn: sqlite3.Connection, table_name: str, row_id: int, content_hash: str) -> bool:
        """Check if this row is already embedded with the same content."""
        row = conn.execute(
            "SELECT content_hash FROM embeddings_meta WHERE table_name = ? AND row_id = ?",
            (table_name, row_id),
        ).fetchone()
        return row is not None and row["content_hash"] == content_hash

    def _upsert_embedding(self, conn: sqlite3.Connection, vec_table: str, table_name: str,
                          row_id: int, embedding: list[float], content_hash: str):
        """Insert or update an embedding in the vec table and metadata."""
        serialized = _serialize_f32(embedding)

        # Check if row already exists in metadata
        existing = conn.execute(
            "SELECT id FROM embeddings_meta WHERE table_name = ? AND row_id = ?",
            (table_name, row_id),
        ).fetchone()

        if existing:
            # Update existing: delete old vec row and re-insert
            vec_rowid = existing["id"]
            conn.execute(f"DELETE FROM {vec_table} WHERE rowid = ?", (vec_rowid,))
            conn.execute(
                f"INSERT INTO {vec_table}(rowid, embedding) VALUES (?, ?)",
                (vec_rowid, serialized),
            )
            conn.execute(
                "UPDATE embeddings_meta SET content_hash = ?, created_at = datetime('now') WHERE id = ?",
                (content_hash, vec_rowid),
            )
        else:
            # Insert new
            conn.execute(
                "INSERT INTO embeddings_meta (table_name, row_id, content_hash) VALUES (?, ?, ?)",
                (table_name, row_id, content_hash),
            )
            meta_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                f"INSERT INTO {vec_table}(rowid, embedding) VALUES (?, ?)",
                (meta_id, serialized),
            )

    # ─────────────────────────────────────────
    # Public: embed individual items
    # ─────────────────────────────────────────

    def embed_conversation(self, conv_id: int, content: str) -> bool:
        """Embed a single conversation entry. Returns True if embedded."""
        if not self._vec_available:
            return False
        try:
            content_hash = self._content_hash(content)
            conn = self._get_conn()
            try:
                if self._is_already_embedded(conn, "conversations", conv_id, content_hash):
                    return False
                embedding = self._get_embedding(content)
                if embedding is None:
                    return False
                self._upsert_embedding(conn, "vec_conversations", "conversations", conv_id, embedding, content_hash)
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log.error(f"embed_conversation({conv_id}) error: {e}")
            return False

    def embed_task(self, task_id: int, title: str, description: str = "", result: str = "") -> bool:
        """Embed a task (title + description + result as one vector)."""
        if not self._vec_available:
            return False
        try:
            parts = [f"Task: {title}"]
            if description:
                parts.append(f"Description: {description}")
            if result:
                parts.append(f"Result: {result}")
            text = "\n".join(parts)
            content_hash = self._content_hash(text)

            conn = self._get_conn()
            try:
                if self._is_already_embedded(conn, "tasks", task_id, content_hash):
                    return False
                embedding = self._get_embedding(text)
                if embedding is None:
                    return False
                self._upsert_embedding(conn, "vec_tasks", "tasks", task_id, embedding, content_hash)
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log.error(f"embed_task({task_id}) error: {e}")
            return False

    def embed_learning(self, learning_id: int, category: str, insight: str) -> bool:
        """Embed a learning (category + insight)."""
        if not self._vec_available:
            return False
        try:
            text = f"[{category}] {insight}"
            content_hash = self._content_hash(text)

            conn = self._get_conn()
            try:
                if self._is_already_embedded(conn, "learnings", learning_id, content_hash):
                    return False
                embedding = self._get_embedding(text)
                if embedding is None:
                    return False
                self._upsert_embedding(conn, "vec_learnings", "learnings", learning_id, embedding, content_hash)
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log.error(f"embed_learning({learning_id}) error: {e}")
            return False

    # ─────────────────────────────────────────
    # Search
    # ─────────────────────────────────────────

    def search(self, query_text: str, tables: list[str] = None, limit: int = 5) -> list[dict]:
        """Semantic search across specified tables (or all).

        Returns: [{table, row_id, distance, content_preview}]
        """
        if not self._vec_available:
            return []

        query_embedding = self._get_embedding(query_text)
        if query_embedding is None:
            return []

        serialized_query = _serialize_f32(query_embedding)

        table_map = {
            "conversations": ("vec_conversations", "conversations", "content"),
            "tasks": ("vec_tasks", "tasks", "title"),
            "learnings": ("vec_learnings", "learnings", "insight"),
        }

        if tables is None:
            tables = list(table_map.keys())

        results = []
        conn = self._get_conn()
        try:
            for tbl_name in tables:
                if tbl_name not in table_map:
                    continue
                vec_table, src_table, preview_col = table_map[tbl_name]

                try:
                    rows = conn.execute(
                        f"""SELECT v.rowid, v.distance, em.row_id
                            FROM {vec_table} v
                            JOIN embeddings_meta em ON em.id = v.rowid
                            WHERE v.embedding MATCH ? AND k = ?
                            ORDER BY v.distance""",
                        (serialized_query, limit),
                    ).fetchall()

                    for row in rows:
                        # Fetch preview from source table
                        src_row = conn.execute(
                            f"SELECT * FROM {src_table} WHERE id = ?",
                            (row["row_id"],),
                        ).fetchone()

                        preview = ""
                        if src_row:
                            if tbl_name == "conversations":
                                preview = f"[{src_row['role']}] {src_row['content'][:200]}"
                            elif tbl_name == "tasks":
                                desc = (src_row['description'] or '') if src_row['description'] else ''
                                preview = f"{src_row['title']}: {desc[:150]}"
                            elif tbl_name == "learnings":
                                preview = f"[{src_row['category']}] {src_row['insight'][:200]}"

                        results.append({
                            "table": tbl_name,
                            "row_id": row["row_id"],
                            "distance": round(row["distance"], 4),
                            "preview": preview,
                        })
                except Exception as e:
                    log.warning(f"Search in {vec_table} failed: {e}")
                    continue
        finally:
            conn.close()

        # Sort all results by distance and limit
        results.sort(key=lambda r: r["distance"])
        return results[:limit]

    # ─────────────────────────────────────────
    # Backfill
    # ─────────────────────────────────────────

    def backfill(self) -> dict:
        """Embed all existing rows that don't have embeddings yet.

        Returns: {conversations: N, tasks: N, learnings: N} with counts of newly embedded items.
        """
        if not self._vec_available:
            return {"conversations": 0, "tasks": 0, "learnings": 0, "error": "not available"}

        stats = {"conversations": 0, "tasks": 0, "learnings": 0}

        conn = self._get_conn()
        src_conn = sqlite3.connect(str(self.db_path))
        src_conn.row_factory = sqlite3.Row
        try:
            # Backfill conversations
            rows = src_conn.execute(
                """SELECT c.id, c.content FROM conversations c
                   WHERE c.id NOT IN (
                       SELECT row_id FROM embeddings_meta WHERE table_name = 'conversations'
                   )
                   ORDER BY c.id"""
            ).fetchall()

            for batch_start in range(0, len(rows), BATCH_SIZE):
                batch = rows[batch_start:batch_start + BATCH_SIZE]
                texts = [r["content"] for r in batch]
                embeddings = self._get_embeddings_batch(texts)
                for row, emb in zip(batch, embeddings):
                    if emb is None:
                        continue
                    content_hash = self._content_hash(row["content"])
                    self._upsert_embedding(conn, "vec_conversations", "conversations", row["id"], emb, content_hash)
                    stats["conversations"] += 1
                conn.commit()

            # Backfill tasks
            rows = src_conn.execute(
                """SELECT t.id, t.title, t.description, t.result FROM tasks t
                   WHERE t.id NOT IN (
                       SELECT row_id FROM embeddings_meta WHERE table_name = 'tasks'
                   )
                   ORDER BY t.id"""
            ).fetchall()

            for batch_start in range(0, len(rows), BATCH_SIZE):
                batch = rows[batch_start:batch_start + BATCH_SIZE]
                texts = []
                for r in batch:
                    parts = [f"Task: {r['title']}"]
                    if r["description"]:
                        parts.append(f"Description: {r['description']}")
                    if r["result"]:
                        parts.append(f"Result: {r['result']}")
                    texts.append("\n".join(parts))

                embeddings = self._get_embeddings_batch(texts)
                for row, text, emb in zip(batch, texts, embeddings):
                    if emb is None:
                        continue
                    content_hash = self._content_hash(text)
                    self._upsert_embedding(conn, "vec_tasks", "tasks", row["id"], emb, content_hash)
                    stats["tasks"] += 1
                conn.commit()

            # Backfill learnings
            rows = src_conn.execute(
                """SELECT l.id, l.category, l.insight FROM learnings l
                   WHERE l.id NOT IN (
                       SELECT row_id FROM embeddings_meta WHERE table_name = 'learnings'
                   )
                   ORDER BY l.id"""
            ).fetchall()

            for batch_start in range(0, len(rows), BATCH_SIZE):
                batch = rows[batch_start:batch_start + BATCH_SIZE]
                texts = [f"[{r['category']}] {r['insight']}" for r in batch]
                embeddings = self._get_embeddings_batch(texts)
                for row, text, emb in zip(batch, texts, embeddings):
                    if emb is None:
                        continue
                    content_hash = self._content_hash(text)
                    self._upsert_embedding(conn, "vec_learnings", "learnings", row["id"], emb, content_hash)
                    stats["learnings"] += 1
                conn.commit()

        except Exception as e:
            log.error(f"Backfill error: {e}")
            stats["error"] = str(e)
        finally:
            conn.close()
            src_conn.close()

        return stats

    # ─────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get embedding coverage statistics."""
        if not self._vec_available:
            return {"available": False}

        conn = self._get_conn()
        src_conn = sqlite3.connect(str(self.db_path))
        src_conn.row_factory = sqlite3.Row
        try:
            stats = {"available": True}
            for table_name in ("conversations", "tasks", "learnings"):
                embedded = conn.execute(
                    "SELECT COUNT(*) as cnt FROM embeddings_meta WHERE table_name = ?",
                    (table_name,),
                ).fetchone()["cnt"]
                total = src_conn.execute(
                    f"SELECT COUNT(*) as cnt FROM {table_name}"
                ).fetchone()["cnt"]
                stats[table_name] = {"embedded": embedded, "total": total}
            return stats
        except Exception as e:
            return {"available": True, "error": str(e)}
        finally:
            conn.close()
            src_conn.close()
