from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from cv_agent.config import Settings


@dataclass(frozen=True)
class CvDocumentText:
    """Full CV text reconstructed from Qdrant chunk payloads."""

    cv_id: str
    text: str
    truncated: bool
    chunk_count: int


def fetch_cv_document_text(
    client: QdrantClient,
    settings: Settings,
    cv_id: str,
    *,
    max_chars: int,
) -> CvDocumentText:
    """
    Scroll all points for ``cv_id``, order by ``chunk_index``, concatenate ``text``.

    Truncates to ``max_chars`` and sets ``truncated`` when content was cut.
    """
    stripped = cv_id.strip()
    if not stripped:
        return CvDocumentText(cv_id=cv_id, text="", truncated=False, chunk_count=0)

    flt = qm.Filter(
        must=[qm.FieldCondition(key="cv_id", match=qm.MatchValue(value=stripped))],
    )

    rows: list[tuple[int, str]] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.qdrant_collection_name,
            scroll_filter=flt,
            limit=256,
            offset=offset,
            with_payload=True,
        )
        for pt in points:
            if pt.payload is None:
                continue
            pl: dict[str, Any] = dict(pt.payload)
            raw_idx = pl.get("chunk_index")
            try:
                idx = int(raw_idx) if raw_idx is not None else 0
            except (TypeError, ValueError):
                idx = 0
            t = pl.get("text")
            text = t if isinstance(t, str) else ""
            rows.append((idx, text))
        if offset is None:
            break

    rows.sort(key=lambda x: (x[0], x[1][:20]))
    parts: list[str] = []
    for _, t in rows:
        if t:
            parts.append(t)

    full = "\n\n".join(parts)
    truncated = len(full) > max_chars
    out = full[:max_chars] if truncated else full
    return CvDocumentText(
        cv_id=stripped,
        text=out,
        truncated=truncated,
        chunk_count=len(rows),
    )
