from __future__ import annotations

from collections import defaultdict
from typing import Any


def collapse_by_cv_id(
    hits: list[tuple[float, dict[str, Any]]],
    *,
    top_k_cvs: int,
    chunks_per_cv: int,
) -> list[tuple[str, float, list[tuple[float, dict[str, Any]]]]]:
    """
    Collapse Qdrant chunk hits to unique CVs.

    - CV-level score = max chunk score for that CV.
    - CVs sorted by score descending, then cv_id ascending (stable tie-break).
    - Per CV: top ``chunks_per_cv`` chunks by score, deduplicated by chunk_index.
    """
    by_cv: dict[str, list[tuple[float, dict[str, Any]]]] = defaultdict(list)
    for score, payload in hits:
        raw_id = payload.get("cv_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            continue
        by_cv[raw_id].append((score, payload))

    rows: list[tuple[str, float, list[tuple[float, dict[str, Any]]]]] = []
    for cv_id, cv_hits in by_cv.items():
        if not cv_hits:
            continue
        cv_hits_by_score = sorted(
            cv_hits,
            key=lambda x: (-x[0], x[1].get("chunk_index", 0)),
        )
        max_score = max(s for s, _ in cv_hits)

        seen_idx: set[int] = set()
        top_chunks: list[tuple[float, dict[str, Any]]] = []
        for score, pl in cv_hits_by_score:
            raw_idx = pl.get("chunk_index")
            if raw_idx is None:
                continue
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                continue
            if idx in seen_idx:
                continue
            seen_idx.add(idx)
            top_chunks.append((score, pl))
            if len(top_chunks) >= chunks_per_cv:
                break

        rows.append((cv_id, max_score, top_chunks))

    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows[:top_k_cvs]
