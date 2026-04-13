from __future__ import annotations

from openai import AsyncAzureOpenAI, AsyncOpenAI

from cv_agent.config import Settings


def build_async_openai_chat_client(settings: Settings) -> AsyncOpenAI | AsyncAzureOpenAI:
    """Async OpenAI SDK client for chat, aligned with ``llm_provider``."""
    if settings.llm_provider == "azure_foundry":
        from cv_agent.foundry_openai import async_openai_client_from_settings

        return async_openai_client_from_settings(settings, for_llm=True)

    if settings.llm_provider == "azure_openai":
        endpoint = settings.llm_base_url.strip().rstrip("/")
        if not endpoint:
            raise ValueError("LLM_BASE_URL is required when LLM_PROVIDER=azure_openai")
        ver = (settings.llm_api_version or "").strip() or "2024-02-01"
        return AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_version=ver,
            api_key=settings.llm_api_key,
            azure_deployment=settings.llm_model,
        )

    base = (settings.llm_base_url or "").strip() or None
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=base,
    )
