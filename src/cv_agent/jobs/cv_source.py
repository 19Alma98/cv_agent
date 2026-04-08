from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CVRecord:
    cv_id: str
    path: Path
    updated_at: datetime


def _parse_iso8601(s: str) -> datetime:
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return t.astimezone(UTC)


def _mtime_utc(path: Path) -> datetime:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=UTC)


def load_cv_records(root: Path) -> list[CVRecord]:
    """
    Load CV records from ``manifest.json`` if present, else discover ``*.pdf`` under root.

    Manifest format::

        {
          "cvs": [
            {"cv_id": "alice", "file": "folder/alice.pdf", "updated_at": "2025-01-01T00:00:00Z"}
          ]
        }

    ``file`` is relative to ``root``. ``updated_at`` is optional (defaults to file mtime).
    """
    root = root.resolve()
    manifest_path = root / "manifest.json"
    records: list[CVRecord] = []

    if manifest_path.is_file():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = data.get("cvs") or data.get("items") or []
        if not isinstance(entries, list):
            raise ValueError("manifest.json: expected a list under 'cvs' or 'items'")
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            cv_id = str(raw.get("cv_id") or raw.get("id") or "").strip()
            rel = raw.get("file") or raw.get("path") or raw.get("relative_path")
            if not cv_id or not rel:
                logger.warning("manifest entry missing cv_id or file, skipping: %s", raw)
                continue
            path = (root / str(rel)).resolve()
            if not path.is_file():
                logger.warning("manifest entry file missing: %s", path)
                continue
            upd_raw = raw.get("updated_at")
            if upd_raw:
                updated = _parse_iso8601(str(upd_raw))
            else:
                updated = _mtime_utc(path)
            records.append(CVRecord(cv_id=cv_id, path=path, updated_at=updated))
        return records

    for pdf in sorted(root.rglob("*.pdf")):
        if not pdf.is_file():
            continue
        rel = pdf.relative_to(root)
        cv_id = str(rel.with_suffix("")).replace("/", "__")
        records.append(CVRecord(cv_id=cv_id, path=pdf.resolve(), updated_at=_mtime_utc(pdf)))

    return records


def filter_records(
    records: list[CVRecord],
    *,
    since: datetime | None,
    cv_id: str | None,
) -> list[CVRecord]:
    out = records
    if cv_id is not None:
        out = [r for r in out if r.cv_id == cv_id]
    if since is not None:
        since_utc = since.astimezone(UTC)
        out = [r for r in out if r.updated_at >= since_utc]
    return out
