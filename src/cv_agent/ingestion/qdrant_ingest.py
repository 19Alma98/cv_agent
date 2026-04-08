from __future__ import annotations

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from cv_agent.config import Settings


# Deterministic point ids (idempotent upserts).
_POINT_NAMESPACE = uuid.UUID("018f3a8e-7c2b-7b8a-9c1d-4e2f0a1b2c3d")


def stable_point_uuid(ingestion_version: str, cv_id: str, chunk_index: int) -> str:
    key = f"{ingestion_version}:{cv_id}:{chunk_index}"
    return str(uuid.uuid5(_POINT_NAMESPACE, key))


@dataclass(frozen=True)
class ChunkPayload:
    cv_id: str
    chunk_index: int
    text: str
    ingestion_version: str
    embedding_model_id: str
    source: str | None = None


def ensure_collection(client: QdrantClient, settings: Settings) -> None:
    name = settings.qdrant_collection_name
    size = settings.embedding_vector_size
    exists = False
    cols = client.get_collections().collections
    exists = any(c.name == name for c in cols)
    if exists:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(size=size, distance=qm.Distance.COSINE),
    )


def recreate_collection(client: QdrantClient, settings: Settings) -> None:
    name = settings.qdrant_collection_name
    size = settings.embedding_vector_size
    client.recreate_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(size=size, distance=qm.Distance.COSINE),
    )


def delete_points_for_cv(client: QdrantClient, settings: Settings, cv_id: str) -> None:
    """Remove existing points so re-ingestion does not leave orphaned chunks."""
    client.delete(
        collection_name=settings.qdrant_collection_name,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[qm.FieldCondition(key="cv_id", match=qm.MatchValue(value=cv_id))]
            )
        ),
    )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=60),
    reraise=True,
)
def _upsert_batch(
    client: QdrantClient,
    collection: str,
    points: list[qm.PointStruct],
) -> None:
    client.upsert(collection_name=collection, points=points)


def upsert_chunks(
    client: QdrantClient,
    settings: Settings,
    items: list[tuple[list[float], ChunkPayload]],
    *,
    upsert_batch_size: int = 128,
) -> None:
    collection = settings.qdrant_collection_name
    batch: list[qm.PointStruct] = []

    for vector, payload in items:
        pid = stable_point_uuid(payload.ingestion_version, payload.cv_id, payload.chunk_index)
        pl = {
            "cv_id": payload.cv_id,
            "chunk_index": payload.chunk_index,
            "text": payload.text,
            "ingestion_version": payload.ingestion_version,
            "embedding_model_id": payload.embedding_model_id,
        }
        if payload.source is not None:
            pl["source"] = payload.source
        batch.append(
            qm.PointStruct(
                id=pid,
                vector=vector,
                payload=pl,
            )
        )
        if len(batch) >= upsert_batch_size:
            _upsert_batch(client, collection, batch)
            batch = []

    if batch:
        _upsert_batch(client, collection, batch)
