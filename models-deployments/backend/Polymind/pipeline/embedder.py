# embedder.py
import os

os.environ.setdefault("HF_HOME", "/app/.cache/huggingface")
os.environ.setdefault("TRANSFORMERS_CACHE", "/app/.cache/huggingface")
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/app/.cache/huggingface")

import logging
from dataclasses import dataclass, field

import numpy as np
import torch

from Polymind.pipeline.chunker import Chunk

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"


@dataclass
class Vector:
    chunk_id: str
    doc_id: str
    page_number: int
    chunk_index: int
    text: str
    embedding: np.ndarray = field(repr=False)


class Embedder:
    def __init__(self, model_name: str = _DEFAULT_MODEL):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            ) from e

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading embedding model: {model_name} on {device}")
        self._model = SentenceTransformer(model_name, device=device)
        self._model_name = model_name
        self._dim: int = self._model.get_sentence_embedding_dimension() or 384
        logger.info(f"Embedding model ready — dim={self._dim}")

    def embed(self, chunks: list[Chunk]) -> list[Vector]:
        if not chunks:
            logger.warning("embed() called with empty chunk list.")
            return []

        texts = [c.text for c in chunks]

        logger.info(f"Embedding {len(texts)} chunk(s) with {self._model_name} ...")
        raw = self._model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        embeddings: np.ndarray = np.array(raw, dtype=np.float32)

        vectors = [
            Vector(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                text=c.text,
                embedding=embeddings[i],
            )
            for i, c in enumerate(chunks)
        ]

        logger.info(f"Embedded {len(vectors)} vector(s) — dim=({self._dim},)")
        return vectors

    def embed_query(self, text: str) -> np.ndarray:
        logger.info(f"Embedding query: '{text[:80]}{'...' if len(text) > 80 else ''}'")
        raw = self._model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=1,
        )
        return np.array(raw[0], dtype=np.float32)

    @property
    def dim(self) -> int:
        return self._dim