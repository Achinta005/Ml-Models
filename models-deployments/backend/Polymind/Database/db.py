import logging
import asyncpg

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection pool — initialised once at app startup
# ---------------------------------------------------------------------------
_pool: asyncpg.Pool | None = None


async def connect():
    """Create the connection pool. Call once in FastAPI startup event."""
    global _pool
    _pool = await asyncpg.create_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
        server_settings={"search_path": settings.POSTGRES_SCHEMA},
        min_size=2,
        max_size=10,
    )
    logger.info("PostgreSQL pool created.")


async def disconnect():
    """Close the connection pool. Call once in FastAPI shutdown event."""
    global _pool
    if _pool:
        await _pool.close()
        logger.info("PostgreSQL pool closed.")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool is not initialised. Call connect() first.")
    return _pool


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id           TEXT        PRIMARY KEY,
    user_id      TEXT        NOT NULL,
    filename     TEXT        NOT NULL,
    size_bytes   BIGINT      NOT NULL DEFAULT 0,
    status       TEXT        NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);

CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT        PRIMARY KEY,          -- chunk_id (uuid)
    doc_id       TEXT        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id      TEXT        NOT NULL,
    page_number  INTEGER     NOT NULL,
    chunk_index  INTEGER     NOT NULL,
    token_count  INTEGER     NOT NULL,
    text         TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id   ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_user_id  ON chunks(user_id);
"""


async def create_tables():
    """Create tables if they don't exist. Safe to call on every startup."""
    async with get_pool().acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
    logger.info("DB tables verified / created.")


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------
async def insert_document(
    doc_id: str, user_id: str, filename: str, size_bytes: int = 0
) -> None:
    sql = """
        INSERT INTO documents (id, user_id, filename, size_bytes, status)
        VALUES ($1, $2, $3, $4, 'processing')
        ON CONFLICT (id) DO NOTHING
    """
    async with get_pool().acquire() as conn:
        await conn.execute(sql, doc_id, user_id, filename, size_bytes)
    logger.info(f"[{doc_id}] Document row inserted. size - {size_bytes}")


async def update_status(doc_id: str, status: str) -> None:
    """Update document ingestion status (processing | ready | error)."""
    sql = "UPDATE documents SET status = $1 WHERE id = $2"
    async with get_pool().acquire() as conn:
        await conn.execute(sql, status, doc_id)
    logger.info(f"[{doc_id}] Status → {status}")


async def get_user_documents(user_id: str) -> list[dict]:
    """Return all documents belonging to a user."""
    sql = """
        SELECT id, filename,size_bytes, status, created_at
        FROM documents
        WHERE user_id = $1
        ORDER BY created_at DESC
    """
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(sql, user_id)
    return [dict(r) for r in rows]


async def get_ready_doc_ids(user_id: str) -> list[str]:
    """
    Return doc_ids of all READY documents for a user.
    Used to scope FAISS search to only the user's indexed documents.
    """
    sql = """
        SELECT id FROM documents
        WHERE user_id = $1 AND status = 'ready'
    """
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(sql, user_id)
    return [r["id"] for r in rows]


async def get_document_status(doc_id: str) -> dict | None:
    sql = "SELECT id, status FROM documents WHERE id = $1"
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(sql, doc_id)
    result = dict(row) if row else None
    return result


async def get_user_total_storage(user_id: str) -> int:
    """Return total size_bytes of all documents for a user."""
    sql = "SELECT COALESCE(SUM(size_bytes), 0) FROM documents WHERE user_id = $1"
    async with get_pool().acquire() as conn:
        total = await conn.fetchval(sql, user_id)
    return int(total)


async def delete_document(doc_id: str, user_id: str) -> bool:
    """Delete document + chunks (CASCADE) + FAISS index files."""
    sql = "DELETE FROM documents WHERE id = $1 AND user_id = $2 RETURNING id"
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(sql, doc_id, user_id)
    if row:
        logger.info(f"[{doc_id}] Document and chunks deleted from DB.")
        return True
    return False


# ---------------------------------------------------------------------------
# Chunk operations
# ---------------------------------------------------------------------------
async def save_chunks(chunks, embedding_ids: list[str], user_id: str) -> None:
    """
    Bulk-insert chunk rows.

    Args:
        chunks:        List of Chunk objects from chunker.chunk().
        embedding_ids: List of chunk_ids returned by indexer.add_and_persist()
                       — used to verify alignment, not stored separately.
        user_id:       Passed directly from run_pipeline — avoids a redundant DB lookup.
    """
    if not chunks:
        return

    doc_id = chunks[0].doc_id

    async with get_pool().acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO chunks
                (id, doc_id, user_id, page_number, chunk_index, token_count, text)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO NOTHING
            """,
            [
                (
                    c.chunk_id,
                    c.doc_id,
                    user_id,
                    c.page_number,
                    c.chunk_index,
                    c.token_count,
                    c.text,
                )
                for c in chunks
            ],
        )

    logger.info(f"[{doc_id}] Saved {len(chunks)} chunk(s) to DB.")


async def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    """
    Fetch full chunk rows by a list of chunk_ids.
    Used after FAISS search to hydrate results with DB metadata.
    """
    sql = """
        SELECT id, doc_id, user_id, page_number, chunk_index, text
        FROM chunks
        WHERE id = ANY($1::text[])
    """
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(sql, chunk_ids)
    return [dict(r) for r in rows]
