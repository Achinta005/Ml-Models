import logging
import json
import asyncio
import pickle
from pathlib import Path
import numpy as np
from sklearn.neighbors import NearestNeighbors

logger = logging.getLogger(__name__)

_DEFAULT_INDEX_DIR = "sklearn_indexes"
_DEFAULT_TOP_K = 3


class Indexer:
    def __init__(self, index_dir: str = _DEFAULT_INDEX_DIR):
        self._index_dir = Path(index_dir)
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple] = {}  # doc_id -> (model, metadata)

    # ── Ingestion ─────────────────────────────────────────────
    async def add_and_persist(self, vectors: list) -> list[str]:
        if not vectors:
            logger.warning("add_and_persist() called with empty vector list.")
            return []

        doc_id = vectors[0].doc_id
        dim = vectors[0].embedding.shape[0]

        matrix = np.stack([v.embedding for v in vectors]).astype("float32")

        # Train KDTree-based nearest neighbors model
        n_neighbors = min(10, len(vectors))
        model = NearestNeighbors(
            n_neighbors=n_neighbors,
            algorithm="kd_tree",
            metric="cosine",
        )
        model.fit(matrix)

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

        index_path = self._index_dir / f"{doc_id}.pkl"
        meta_path = self._index_dir / f"{doc_id}.meta.json"

        # Offload blocking file I/O off the event loop
        await asyncio.to_thread(
            lambda: index_path.write_bytes(pickle.dumps(model))
        )
        await asyncio.to_thread(
            meta_path.write_text,
            json.dumps(metadata, ensure_ascii=False, indent=2),
            "utf-8",
        )

        self._cache[doc_id] = (model, metadata)

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
        model, metadata = self._load_for_doc(doc_id)

        q = query_vector.astype("float32").reshape(1, -1)
        k = min(top_k, len(metadata))

        # KDTree returns distances; for cosine metric, higher distance = lower similarity
        distances, indices = model.kneighbors(q, n_neighbors=k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            entry = dict(metadata[idx])
            # Convert distance to similarity score (0-1, where 1 is most similar)
            entry["score"] = float(1.0 / (1.0 + dist))
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
            logger.debug(f"[{doc_id}] Using cached index")
            return self._cache[doc_id]

        index_path = self._index_dir / f"{doc_id}.pkl"
        meta_path = self._index_dir / f"{doc_id}.meta.json"

        if not index_path.exists():
            raise FileNotFoundError(
                f"No index found for doc_id='{doc_id}'. Expected: {index_path}"
            )

        model = pickle.loads(index_path.read_bytes())
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        self._cache[doc_id] = (model, metadata)

        logger.info(
            f"[{doc_id}] Loaded index from disk — {len(metadata)} vector(s)"
        )
        return model, metadata

    def index_exists(self, doc_id: str) -> bool:
        return (self._index_dir / f"{doc_id}.pkl").exists()

    def delete(self, doc_id: str) -> None:
        for suffix in (".pkl", ".meta.json"):
            path = self._index_dir / f"{doc_id}{suffix}"
            if path.exists():
                path.unlink()

        self._cache.pop(doc_id, None)
        logger.info(f"[{doc_id}] Index deleted.")