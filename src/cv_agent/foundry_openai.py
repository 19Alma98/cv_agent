from __future__ import annotations

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncOpenAI, OpenAI

from cv_agent.config import Settings


def openai_client_for_foundry_project(endpoint: str) -> OpenAI:
    """
    ``endpoint`` is the Foundry **project** URL (e.g. ``AZURE_PROJECT_ENDPOINT`` in your
    other repo), not ``*.openai.azure.com``.
    """
    ep = endpoint.strip().rstrip("/")
    if not ep:
        raise ValueError("Foundry project endpoint is empty")
    project = AIProjectClient(endpoint=ep, credential=DefaultAzureCredential())
    return project.get_openai_client()


def openai_client_from_settings(settings: Settings, *, for_llm: bool) -> OpenAI:
    """Build a Foundry-scoped OpenAI SDK client when provider is ``azure_foundry``."""
    ep = settings.azure_ai_project_endpoint.strip()
    if for_llm:
        if settings.llm_provider != "azure_foundry":
            ep = ep + "/api/projects/ms-foundry-test-01"
            raise ValueError("LLM_PROVIDER must be azure_foundry")
    elif settings.embedding_provider != "azure_foundry":
        raise ValueError("EMBEDDING_PROVIDER must be azure_foundry")
    if not ep:
        raise ValueError("AZURE_AI_PROJECT_ENDPOINT is required for azure_foundry")
    return openai_client_for_foundry_project(ep)


def async_openai_client_from_settings(settings: Settings, *, for_llm: bool) -> AsyncOpenAI:
    """Foundry AsyncOpenAI for Agent Framework (async ``chat.completions.create``)."""
    ep = settings.azure_ai_project_endpoint.strip()
    if for_llm:
        if settings.llm_provider != "azure_foundry":
            raise ValueError("LLM_PROVIDER must be azure_foundry")
    elif settings.embedding_provider != "azure_foundry":
        raise ValueError("EMBEDDING_PROVIDER must be azure_foundry")
    if not ep:
        raise ValueError("AZURE_AI_PROJECT_ENDPOINT is required for azure_foundry")
    base_url = ep.rstrip("/") + "/openai/v1"
    credential = DefaultAzureCredential()
    sync_token = get_bearer_token_provider(credential, "https://ai.azure.com/.default")

    async def api_key_provider() -> str:
        return sync_token()

    return AsyncOpenAI(api_key=api_key_provider, base_url=base_url)
