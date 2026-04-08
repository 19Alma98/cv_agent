from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from cv_agent.config import Settings
from cv_agent.foundry_openai import openai_client_from_settings
from cv_agent.openai_endpoints import (
    embeddings_headers,
    embeddings_request_body,
    embeddings_url,
)


class EmbeddingError(RuntimeError):
    pass


def _embed_texts_foundry_project(
    texts: list[str],
    settings: Settings,
    *,
    batch_size: int,
) -> list[list[float]]:
    oai = openai_client_from_settings(settings, for_llm=False)
    expected = settings.embedding_vector_size
    all_vectors: list[list[float]] = []

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        reraise=True,
    )
    def create_batch(batch: list[str]):
        return oai.embeddings.create(model=settings.embedding_model, input=batch)

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch = [t.replace("\n", " ") for t in batch]
        resp = create_batch(batch)
        items = sorted(resp.data, key=lambda d: d.index)
        if len(items) != len(batch):
            raise EmbeddingError("Embedding API returned unexpected number of vectors")
        for row in items:
            vec = list(row.embedding)
            if len(vec) != expected:
                raise EmbeddingError(
                    f"Embedding dimension {len(vec)} != configured EMBEDDING_VECTOR_SIZE={expected}"
                )
            all_vectors.append([float(x) for x in vec])

    return all_vectors


def _make_post_embeddings(settings: Settings):
    url = embeddings_url(settings)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        reraise=True,
    )
    def _post(client: httpx.Client, payload: dict[str, Any]) -> dict[str, Any]:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()

    return _post


def embed_texts(
    texts: list[str],
    settings: Settings,
    *,
    batch_size: int = 64,
) -> list[list[float]]:
    """
    Embeddings via HTTP (OpenAI / Azure OpenAI) or via Foundry project OpenAI SDK.
    """
    if not settings.embedding_model:
        raise EmbeddingError("EMBEDDING_MODEL is required for ingestion")

    if settings.embedding_provider == "azure_foundry":
        if not settings.azure_ai_project_endpoint.strip():
            raise EmbeddingError(
                "AZURE_AI_PROJECT_ENDPOINT is required when EMBEDDING_PROVIDER=azure_foundry"
            )
        return _embed_texts_foundry_project(texts, settings, batch_size=batch_size)

    if not settings.embedding_api_key:
        raise EmbeddingError("EMBEDDING_API_KEY is required for ingestion")
    if settings.embedding_provider == "azure_openai" and not (
        settings.embedding_base_url or ""
    ).strip():
        raise EmbeddingError(
            "EMBEDDING_BASE_URL is required when EMBEDDING_PROVIDER=azure_openai "
            "(e.g. https://YOUR_RESOURCE.openai.azure.com)"
        )

    headers = embeddings_headers(settings)
    expected = settings.embedding_vector_size
    all_vectors: list[list[float]] = []

    post = _make_post_embeddings(settings)
    with httpx.Client(timeout=120.0, headers=headers) as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            # Some models recommend replacing newlines for consistency with queries.
            batch = [t.replace("\n", " ") for t in batch]
            body = embeddings_request_body(settings, batch)
            data = post(client, body)
            items = data.get("data") or []
            if len(items) != len(batch):
                raise EmbeddingError("Embedding API returned unexpected number of vectors")
            items = sorted(items, key=lambda x: x.get("index", 0))
            for row in items:
                vec = row.get("embedding")
                if not isinstance(vec, list) or not vec:
                    raise EmbeddingError("Invalid embedding vector in API response")
                if len(vec) != expected:
                    raise EmbeddingError(
                        f"Embedding dimension {len(vec)} != configured EMBEDDING_VECTOR_SIZE={expected}"
                    )
                all_vectors.append([float(x) for x in vec])

    return all_vectors
