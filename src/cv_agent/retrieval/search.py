from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient

from cv_agent.config import Settings
from cv_agent.ingestion.embed import EmbeddingError, embed_query
from cv_agent.retrieval.collapse import collapse_by_cv_id
from cv_agent.retrieval.models import ChunkHit, CvHit, RetrievalMeta, RetrievalResult


class RetrievalServiceError(RuntimeError):
    """Qdrant or upstream failure during retrieval."""


def search_cvs(
    query: str,
    settings: Settings,
    qdrant: QdrantClient,
    *,
    top_k_cvs: int = 20,
    top_k_chunks: int = 80,
    filters: dict[str, Any] | None = None,
    chunks_per_cv: int | None = None,
) -> RetrievalResult:
    """
    Embed ``query``, search Qdrant with limit ``top_k_chunks``, collapse by ``cv_id``.

    ``filters`` is reserved for Phase 3 / metadata filters and is not implemented in Phase 2.
    """
    if filters is not None:
        raise ValueError("filters are not supported in Phase 2 retrieval")

    stripped = query.strip()
    if not stripped:
        raise ValueError("query must be non-empty")

    if top_k_cvs > settings.search_max_limit_cvs:
        raise ValueError(
            f"top_k_cvs={top_k_cvs} exceeds search_max_limit_cvs={settings.search_max_limit_cvs}"
        )
    if top_k_chunks > settings.search_max_limit_chunks:
        raise ValueError(
            f"top_k_chunks={top_k_chunks} exceeds "
            f"search_max_limit_chunks={settings.search_max_limit_chunks}"
        )

    n_chunks = chunks_per_cv if chunks_per_cv is not None else settings.search_chunks_per_cv

    try:
        vector = embed_query(stripped, settings)
    except EmbeddingError as e:
        raise RetrievalServiceError(str(e)) from e

    try:
        response = qdrant.query_points(
            collection_name=settings.qdrant_collection_name,
            query=vector,
            limit=top_k_chunks,
            with_payload=True,
        )
    except Exception as e:
        raise RetrievalServiceError(f"qdrant_search_failed: {e}") from e

    raw_hits: list[tuple[float, dict[str, Any]]] = []
    for pt in response.points:
        if pt.payload is None:
            continue
        raw_hits.append((float(pt.score), dict(pt.payload)))

    collapsed = collapse_by_cv_id(
        raw_hits,
        top_k_cvs=top_k_cvs,
        chunks_per_cv=n_chunks,
    )

    cvs: list[CvHit] = []
    for cv_id, cv_score, chunk_rows in collapsed:
        chunks: list[ChunkHit] = []
        for ch_score, pl in chunk_rows:
            raw_idx = pl.get("chunk_index")
            try:
                chunk_index = int(raw_idx) if raw_idx is not None else -1
            except (TypeError, ValueError):
                chunk_index = -1
            text = pl.get("text")
            text_str = text if isinstance(text, str) else ""
            src = pl.get("source")
            source = src if isinstance(src, str) else None
            chunks.append(
                ChunkHit(
                    chunk_index=chunk_index,
                    score=float(ch_score),
                    text=text_str,
                    source=source,
                )
            )
        cvs.append(CvHit(cv_id=cv_id, score=float(cv_score), chunks=chunks))

    meta = RetrievalMeta(
        embedding_model_id=settings.embedding_model or "",
        k_prime=top_k_chunks,
        k=top_k_cvs,
    )
    return RetrievalResult(query=stripped, cvs=cvs, meta=meta)
