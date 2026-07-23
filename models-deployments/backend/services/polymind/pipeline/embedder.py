import os

os.environ.setdefault("HF_HOME", "/app/.cache/huggingface")

import logging
from dataclasses import dataclass, field

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from services.polymind.pipeline.chunker import Chunk

logger = logging.getLogger(__name__)

_ONNX_MODEL_DIR = os.getenv("ONNX_MODEL_DIR", "/app/.cache/onnx")
_ONNX_REPO = "optimum/all-MiniLM-L6-v2"


@dataclass
class Vector:
    chunk_id: str
    doc_id: str
    page_number: int
    chunk_index: int
    text: str
    embedding: np.ndarray = field(repr=False)


def _mean_pooling(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask = attention_mask[..., np.newaxis].astype(np.float32)
    summed = (token_embeddings * mask).sum(axis=1)
    counts = mask.sum(axis=1).clip(min=1e-9)
    return summed / counts


def _normalize(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True).clip(min=1e-9)
    return embeddings / norms


class Embedder:
    def __init__(self):
        onnx_path = os.path.join(_ONNX_MODEL_DIR, "model.onnx")
        tokenizer_path = os.path.join(_ONNX_MODEL_DIR, "tokenizer.json")

        # Fallback: download at runtime if not baked into image
        if not os.path.exists(onnx_path) or not os.path.exists(tokenizer_path):
            logger.warning("ONNX model not found locally, downloading from HuggingFace...")
            from huggingface_hub import hf_hub_download
            os.makedirs(_ONNX_MODEL_DIR, exist_ok=True)
            onnx_path = hf_hub_download(
                repo_id=_ONNX_REPO,
                filename="model.onnx",
                local_dir=_ONNX_MODEL_DIR,
            )
            tokenizer_path = hf_hub_download(
                repo_id=_ONNX_REPO,
                filename="tokenizer.json",
                local_dir=_ONNX_MODEL_DIR,
            )

        logger.info(f"Loading ONNX model from {onnx_path}")

        sess_options = ort.SessionOptions()
        sess_options.inter_op_num_threads = 2
        sess_options.intra_op_num_threads = 2

        self._session = ort.InferenceSession(
            onnx_path,
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        self._tokenizer = Tokenizer.from_file(tokenizer_path)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=128)
        self._tokenizer.enable_truncation(max_length=128)
        self._dim = 384

        logger.info(f"ONNX embedding model ready — dim={self._dim}")

    def _encode(self, texts: list[str]) -> np.ndarray:
        encoded = self._tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)

        outputs = self._session.run(
            ["last_hidden_state"],
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        pooled = _mean_pooling(outputs[0], attention_mask)
        return _normalize(pooled).astype(np.float32)

    def embed(self, chunks: list[Chunk]) -> list[Vector]:
        if not chunks:
            logger.warning("embed() called with empty chunk list.")
            return []

        texts = [c.text for c in chunks]
        logger.info(f"Embedding {len(texts)} chunk(s)...")

        all_embeddings = []
        for i in range(0, len(texts), 32):
            all_embeddings.append(self._encode(texts[i:i + 32]))
        embeddings = np.concatenate(all_embeddings, axis=0)

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
        logger.info(f"Embedded {len(vectors)} vector(s)")
        return vectors

    def embed_query(self, text: str) -> np.ndarray:
        logger.info(f"Embedding query: '{text[:80]}{'...' if len(text) > 80 else ''}'")
        return self._encode([text])[0]

    @property
    def dim(self) -> int:
        return self._dim