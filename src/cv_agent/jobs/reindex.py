from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from cv_agent.clients.qdrant import get_client
from cv_agent.config import Settings, get_settings
from cv_agent.ingestion.chunk import ChunkStrategy, chunk_text
from cv_agent.ingestion.constants import (
    DEFAULT_CHUNK_OVERLAP_CHARS,
    DEFAULT_CHUNK_SIZE_CHARS,
    PARSER_BACKEND,
    PARSER_VERSION,
)
from cv_agent.ingestion.embed import EmbeddingError, embed_texts
from cv_agent.ingestion.extract import extract_cv_text
from cv_agent.ingestion.normalize import normalize_text
from cv_agent.ingestion.qdrant_ingest import (
    ChunkPayload,
    delete_points_for_cv,
    ensure_collection,
    recreate_collection as qdrant_recreate_collection,
    upsert_chunks,
)
from cv_agent.jobs.cv_source import filter_records, load_cv_records

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_since(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def _ingestion_version(
    *,
    embedding_model: str,
    strategy: ChunkStrategy,
    chunk_size_chars: int,
    chunk_overlap_chars: int,
) -> str:
    if strategy == ChunkStrategy.NONE:
        chunk_part = "whole_doc"
    else:
        chunk_part = f"{chunk_size_chars}c_{chunk_overlap_chars}ov"
    return (
        f"parser-{PARSER_VERSION}_{PARSER_BACKEND}_embed-{embedding_model}_{chunk_part}"
    )


def run(
    settings: Settings,
    *,
    root: Path,
    since: datetime | None,
    cv_id: str | None,
    full: bool,
    wipe_collection: bool,
    chunk_strategy: ChunkStrategy,
    chunk_size_chars: int,
    chunk_overlap_chars: int,
) -> int:
    root = root.resolve()
    if not root.is_dir():
        logger.error("CV root is not a directory: %s", root)
        return 2

    records = load_cv_records(root)
    selected = filter_records(records, since=None if full else since, cv_id=cv_id)

    if not selected:
        logger.warning("No CVs matched filters.")
        return 0

    client = get_client(settings)
    if wipe_collection:
        if not full or cv_id is not None:
            logger.error("--recreate-collection requires --full and no --cv-id.")
            return 2
        qdrant_recreate_collection(client, settings)
    else:
        ensure_collection(client, settings)

    ing_ver = _ingestion_version(
        embedding_model=settings.embedding_model or "unknown",
        strategy=chunk_strategy,
        chunk_size_chars=chunk_size_chars,
        chunk_overlap_chars=chunk_overlap_chars,
    )
    model_id = settings.embedding_model or "unknown"

    ok = 0
    failed = 0
    skipped = 0

    for rec in selected:
        try:
            raw = extract_cv_text(rec.path)
        except Exception as e:
            logger.exception("Extract failed cv_id=%s path=%s: %s", rec.cv_id, rec.path, e)
            failed += 1
            continue

        text = normalize_text(raw)
        if not text:
            logger.warning("Empty text after extract/normalize; skipping cv_id=%s", rec.cv_id)
            skipped += 1
            continue

        pieces = chunk_text(
            text,
            strategy=chunk_strategy,
            chunk_size_chars=chunk_size_chars,
            chunk_overlap_chars=chunk_overlap_chars,
        )
        if not pieces:
            logger.warning("No chunks produced; skipping cv_id=%s", rec.cv_id)
            skipped += 1
            continue

        try:
            vectors = embed_texts(pieces, settings)
        except EmbeddingError as e:
            logger.error("Embedding failed for cv_id=%s: %s", rec.cv_id, e)
            failed += 1
            continue
        except Exception:
            logger.exception("Embedding failed for cv_id=%s", rec.cv_id)
            failed += 1
            continue

        delete_points_for_cv(client, settings, rec.cv_id)
        payloads = [
            ChunkPayload(
                cv_id=rec.cv_id,
                chunk_index=i,
                text=pieces[i],
                ingestion_version=ing_ver,
                embedding_model_id=model_id,
                source=rec.path.suffix.lower().lstrip("."),
            )
            for i in range(len(pieces))
        ]
        upsert_chunks(client, settings, list(zip(vectors, payloads, strict=True)))
        logger.info(
            "Upserted cv_id=%s chunks=%d strategy=%s",
            rec.cv_id,
            len(pieces),
            chunk_strategy.value,
        )
        ok += 1

    logger.info("Done: ok=%d failed=%d skipped=%d", ok, failed, skipped)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Ingest CVs into Qdrant (Phase 1).")
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Directory with manifest.json or PDF files (default: CV_INGEST_ROOT from env)",
    )
    p.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO-8601 timestamp: only CVs with updated_at >= this (manifest or file mtime)",
    )
    p.add_argument("--cv-id", type=str, default=None, help="Process a single cv_id")
    p.add_argument(
        "--full",
        action="store_true",
        help="Ignore --since; reindex all CVs (still respects --cv-id if set)",
    )
    p.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Drop and recreate Qdrant collection (requires --full, no --cv-id)",
    )
    p.add_argument(
        "--chunk-strategy",
        choices=[s.value for s in ChunkStrategy],
        default=ChunkStrategy.NONE.value,
        help="none = one vector per CV (default); fixed = sliding character windows",
    )
    p.add_argument(
        "--chunk-size-chars",
        type=int,
        default=DEFAULT_CHUNK_SIZE_CHARS,
        help="For fixed strategy: target chunk size in characters",
    )
    p.add_argument(
        "--chunk-overlap-chars",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP_CHARS,
        help="For fixed strategy: overlap between consecutive chunks",
    )
    args = p.parse_args(argv)

    settings = get_settings()
    root = args.root or settings.cv_ingest_root
    if root is None:
        logger.error("Set --root or CV_INGEST_ROOT in the environment.")
        sys.exit(2)

    if args.recreate_collection:
        if not args.full or args.cv_id is not None:
            logger.error("--recreate-collection requires --full and must not set --cv-id.")
            sys.exit(2)

    since_dt = _parse_since(args.since) if args.since else None
    strategy = ChunkStrategy(args.chunk_strategy)

    code = run(
        settings,
        root=root,
        since=since_dt,
        cv_id=args.cv_id,
        full=args.full,
        wipe_collection=args.recreate_collection,
        chunk_strategy=strategy,
        chunk_size_chars=args.chunk_size_chars,
        chunk_overlap_chars=args.chunk_overlap_chars,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
