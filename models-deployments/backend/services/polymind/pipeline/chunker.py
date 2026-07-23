import logging
import uuid
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 256  # reduced from 512 → faster LLM input
_DEFAULT_OVERLAP = 32  # reduced from 64  → less redundancy


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    page_number: int
    chunk_index: int
    text: str
    token_count: int


def chunk(
    pages,
    doc_id: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_OVERLAP,
) -> list[Chunk]:

    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
        )

    if not pages:
        logger.warning(f"[{doc_id}] No pages provided to chunker.")
        return []

    # Flatten token stream
    token_stream: list[tuple[str, int]] = []
    for page in pages:
        # Strip extra whitespace before splitting — cleaner tokens
        tokens = page.text.strip().split()
        for tok in tokens:
            token_stream.append((tok, page.page_number))

    if not token_stream:
        logger.warning(f"[{doc_id}] All pages empty — no chunks produced.")
        return []

    step = chunk_size - overlap
    chunks: list[Chunk] = []
    idx = 0

    while idx < len(token_stream):
        window = token_stream[idx : idx + chunk_size]

        tokens_only = [t for t, _ in window]
        text = " ".join(tokens_only)
        page_number = window[0][1]

        # Skip very short chunks — not useful for RAG
        if len(tokens_only) < 20:
            idx += step
            continue

        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                page_number=page_number,
                chunk_index=len(chunks),
                text=text,
                token_count=len(tokens_only),
            )
        )

        idx += step

    logger.info(
        f"[{doc_id}] Chunked {len(pages)} page(s) → {len(chunks)} chunk(s) "
        f"(size={chunk_size}, overlap={overlap})"
    )
    return chunks
