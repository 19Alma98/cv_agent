
from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote, urlencode

from cv_agent.config import Settings

EmbeddingProvider = Literal["openai", "azure_openai", "azure_foundry"]
LlmProvider = Literal["openai", "azure_openai", "azure_foundry"]

# Azure OpenAI REST: deployment in path; api-version required.
_DEFAULT_AZURE_API_VERSION = "2024-02-01"


def _azure_api_version(settings: Settings, *, for_llm: bool) -> str:
    if for_llm:
        v = (settings.llm_api_version or "").strip()
    else:
        v = (settings.embedding_api_version or "").strip()
    return v or _DEFAULT_AZURE_API_VERSION


def embeddings_url(settings: Settings) -> str:
    if settings.embedding_provider == "azure_foundry":
        raise ValueError(
            "EMBEDDING_PROVIDER=azure_foundry uses the Foundry OpenAI SDK, not a raw URL"
        )
    if settings.embedding_provider == "azure_openai":
        base = settings.embedding_base_url.rstrip("/")
        deployment = quote(settings.embedding_model, safe="")
        ver = _azure_api_version(settings, for_llm=False)
        q = urlencode({"api-version": ver})
        return f"{base}/openai/deployments/{deployment}/embeddings?{q}"
    base = (settings.embedding_base_url or "https://api.openai.com/v1").rstrip("/")
    return f"{base}/embeddings"


def embeddings_headers(settings: Settings) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if settings.embedding_provider == "azure_foundry":
        raise ValueError("EMBEDDING_PROVIDER=azure_foundry does not use HTTP header helpers")
    if settings.embedding_provider == "azure_openai":
        h["api-key"] = settings.embedding_api_key
    else:
        h["Authorization"] = f"Bearer {settings.embedding_api_key}"
    return h


def embeddings_request_body(settings: Settings, inputs: list[str]) -> dict[str, Any]:
    if settings.embedding_provider == "azure_foundry":
        raise ValueError("EMBEDDING_PROVIDER=azure_foundry does not use JSON body helpers")
    body: dict[str, Any] = {"input": inputs}
    if settings.embedding_provider == "openai":
        body["model"] = settings.embedding_model
    return body


def chat_completions_url(settings: Settings) -> str:
    if settings.llm_provider == "azure_foundry":
        raise ValueError(
            "LLM_PROVIDER=azure_foundry: use cv_agent.foundry_openai.openai_client_from_settings"
        )
    if settings.llm_provider == "azure_openai":
        if not settings.llm_base_url:
            raise ValueError("LLM_BASE_URL is required when LLM_PROVIDER=azure_openai")
        base = settings.llm_base_url.rstrip("/")
        deployment = quote(settings.llm_model, safe="")
        ver = _azure_api_version(settings, for_llm=True)
        q = urlencode({"api-version": ver})
        return f"{base}/openai/deployments/{deployment}/chat/completions?{q}"
    base = (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")
    return f"{base}/chat/completions"


def chat_completions_headers(settings: Settings) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if settings.llm_provider == "azure_foundry":
        raise ValueError(
            "LLM_PROVIDER=azure_foundry: use cv_agent.foundry_openai.openai_client_from_settings"
        )
    if settings.llm_provider == "azure_openai":
        h["api-key"] = settings.llm_api_key
    else:
        h["Authorization"] = f"Bearer {settings.llm_api_key}"
    return h


def chat_completions_request_body(settings: Settings, **extra: Any) -> dict[str, Any]:
    if settings.llm_provider == "azure_foundry":
        raise ValueError(
            "LLM_PROVIDER=azure_foundry: use openai_client_from_settings(..., for_llm=True)"
        )
    body: dict[str, Any] = dict(extra)
    if settings.llm_provider == "openai":
        body["model"] = settings.llm_model
    return body
