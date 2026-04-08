from __future__ import annotations

from enum import Enum


class ChunkStrategy(str, Enum):
    """How to segment document text before embedding."""

    NONE = "none"
    """One segment: the full normalized document (single vector per CV)."""

    FIXED = "fixed"
    """Sliding window over characters with overlap (approx. token window)."""


def chunk_text(
    text: str,
    *,
    strategy: ChunkStrategy,
    chunk_size_chars: int,
    chunk_overlap_chars: int,
) -> list[str]:
    if strategy == ChunkStrategy.NONE:
        return [text] if text else []

    if strategy != ChunkStrategy.FIXED:
        raise ValueError(f"Unknown chunk strategy: {strategy}")

    if not text:
        return []

    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be positive")
    if chunk_overlap_chars < 0:
        raise ValueError("chunk_overlap_chars must be non-negative")
    if chunk_overlap_chars >= chunk_size_chars:
        raise ValueError("chunk_overlap_chars must be smaller than chunk_size_chars")

    chunks: list[str] = []
    start = 0
    n = len(text)
    step = chunk_size_chars - chunk_overlap_chars

    while start < n:
        end = min(start + chunk_size_chars, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start += step

    return chunks
