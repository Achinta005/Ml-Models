# indexer.py
import logging
import json
import asyncio
import numpy as np
from pathlib import Path

from Polymind.pipeline.embedder import Vector

logger = logging.getLogger(__name__)

_DEFAULT_INDEX_DIR = "faiss_indexes"
_DEFAULT_TOP_K = 3


class Indexer:
    def __init__(self, index_dir: str = _DEFAULT_INDEX_DIR):
        try:
            import faiss
            self._faiss = faiss
        except ImportError as e:
            raise ImportError(
                "faiss-cpu is required. Install with: pip install faiss-cpu"
            ) from e

        self._index_dir = Path(index_dir)
        self._index_dir.mkdir(parents=True, exist_ok=True)

        # Cache up to last N indexes to support multi-doc queries
        self._cache: dict[str, tuple] = {}  # doc_id -> (index, metadata)

    # ── Ingestion ─────────────────────────────────────────────
    async def add_and_persist(self, vectors: list[Vector]) -> list[str]:
        if not vectors:
            logger.warning("add_and_persist() called with empty vector list.")
            return []

        doc_id = vectors[0].doc_id
        dim = vectors[0].embedding.shape[0]

        matrix = np.stack([v.embedding for v in vectors]).astype("float32")

        index = self._faiss.IndexFlatIP(dim)
        index.add(matrix)  # type: ignore[arg-type]

        metadata = [
            {
                "chunk_id": v.chunk_id,
                "doc_id": v.doc_id,
                "page_number": v.page_number,
                "chunk_index": v.chunk_index,
                "text": v.text,
            }
            for v in vectors
        ]

        index_path = self._index_dir / f"{doc_id}.index"
        meta_path  = self._index_dir / f"{doc_id}.meta.json"

        # Offload blocking file I/O off the event loop
        await asyncio.to_thread(self._faiss.write_index, index, str(index_path))
        await asyncio.to_thread(
            meta_path.write_text,
            json.dumps(metadata, ensure_ascii=False, indent=2),
            "utf-8",
        )

        self._cache[doc_id] = (index, metadata)

        logger.info(
            f"[{doc_id}] Indexed {len(vectors)} vector(s) → "
            f"{index_path.name} | dim={dim}"
        )
        return [v.chunk_id for v in vectors]

    # ── Query ─────────────────────────────────────────────────
    def search(
        self,
        query_vector: np.ndarray,
        doc_id: str,
        top_k: int = _DEFAULT_TOP_K,
    ) -> list[dict]:
        index, metadata = self._load_for_doc(doc_id)

        q = query_vector.astype("float32").reshape(1, -1)
        k = min(top_k, index.ntotal)

        distances, labels = index.search(q, k)

        results = []
        for score, idx in zip(distances[0], labels[0]):
            if idx == -1:
                continue
            entry = dict(metadata[idx])
            entry["score"] = float(score)
            results.append(entry)

        if results:
            logger.info(
                f"[{doc_id}] Search returned {len(results)} chunk(s) "
                f"(top score={results[0]['score']:.4f})"
            )
        else:
            logger.warning(f"[{doc_id}] Search returned 0 results")

        return results

    # ── Helpers ───────────────────────────────────────────────
    def _load_for_doc(self, doc_id: str):
        if doc_id in self._cache:
            logger.debug(f"[{doc_id}] Using cached FAISS index")
            return self._cache[doc_id]

        index_path = self._index_dir / f"{doc_id}.index"
        meta_path  = self._index_dir / f"{doc_id}.meta.json"

        if not index_path.exists():
            raise FileNotFoundError(
                f"No FAISS index found for doc_id='{doc_id}'. Expected: {index_path}"
            )

        index    = self._faiss.read_index(str(index_path))
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        self._cache[doc_id] = (index, metadata)

        logger.info(
            f"[{doc_id}] Loaded FAISS index from disk — {index.ntotal} vector(s)"
        )
        return index, metadata

    def index_exists(self, doc_id: str) -> bool:
        return (self._index_dir / f"{doc_id}.index").exists()

    def delete(self, doc_id: str) -> None:
        for suffix in (".index", ".meta.json"):
            path = self._index_dir / f"{doc_id}{suffix}"
            if path.exists():
                path.unlink()

        self._cache.pop(doc_id, None)
        logger.info(f"[{doc_id}] FAISS index deleted.")