from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qdrant_url: str = Field(
        ...,
        description="Qdrant REST base URL, e.g. http://localhost:6333",
    )
    qdrant_api_key: str = Field(
        default="",
        description="Optional API key for managed Qdrant; empty for local dev",
    )

    embedding_api_key: str = Field(default="", description="API key for embedding provider")
    embedding_provider: Literal["openai", "azure_openai", "azure_foundry"] = Field(
        default="openai",
        description=(
            "openai: Bearer + /v1/embeddings. "
            "azure_openai: *.openai.azure.com + api-key. "
            "azure_foundry: AI Foundry project + Entra (see AZURE_AI_PROJECT_ENDPOINT)"
        ),
    )
    azure_ai_project_endpoint: str = Field(
        default="",
        description=(
            "Azure AI Foundry project URL for azure_foundry provider "
            "(OpenAI SDK base …/openai/v1)"
        ),
    )
    embedding_base_url: str = Field(
        default="",
        description=(
            "OpenAI: optional API base (default https://api.openai.com/v1). "
            "Azure: resource URL only, e.g. https://YOUR_RESOURCE.openai.azure.com"
        ),
    )
    embedding_api_version: str = Field(
        default="",
        description="Azure OpenAI only: REST api-version query param (default 2024-02-01 if empty)",
    )
    embedding_model: str = Field(
        default="",
        description="Model id (openai) or deployment name (azure_openai / azure_foundry)",
    )
    embedding_vector_size: int = Field(
        default=1536,
        description="Vector dimension; must match the embedding model and Qdrant collection",
    )
    qdrant_collection_name: str = Field(
        default="cv_chunks",
        description="Qdrant collection for CV chunks / whole-document vectors",
    )

    cv_ingest_root: Path | None = Field(
        default=None,
        description="Directory containing CV files or manifest.json (Phase 1 file source)",
    )

    llm_api_key: str = Field(default="", description="API key for chat model")
    llm_provider: Literal["openai", "azure_openai", "azure_foundry"] = Field(
        default="openai",
        description=(
            "Like embedding_provider; azure_foundry uses AZURE_AI_PROJECT_ENDPOINT + Entra"
        ),
    )
    llm_base_url: str = Field(
        default="",
        description="OpenAI: optional API base. Azure: https://YOUR_RESOURCE.openai.azure.com",
    )
    llm_api_version: str = Field(
        default="",
        description="Azure: chat api-version query param (default 2024-02-01 if empty)",
    )
    llm_model: str = Field(
        default="",
        description="OpenAI: model name. Azure: chat deployment name",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
