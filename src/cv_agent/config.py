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
        default=3072,
        description="Vector dimension; must match the embedding model and Qdrant collection",
    )
    qdrant_collection_name: str = Field(
        default="cv_chunks",
        description="Qdrant collection for CV chunks / whole-document vectors",
    )
    qdrant_timeout: int = Field(
        default=60,
        ge=1,
        description="Qdrant HTTP client timeout in seconds",
    )
    search_max_limit_cvs: int = Field(
        default=100,
        ge=1,
        description="Server cap for limit_cvs / top_k_cvs on search endpoints",
    )
    search_max_limit_chunks: int = Field(
        default=200,
        ge=1,
        description="Server cap for limit_chunks / top_k_chunks (k′) before collapse",
    )
    search_chunks_per_cv: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max chunks returned per CV after collapse (evidence spans)",
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

    discover_w_coverage: float = Field(
        default=0.5,
        ge=0.0,
        description="Weight for normalized skills coverage in composite score",
    )
    discover_w_vector: float = Field(
        default=0.5,
        ge=0.0,
        description="Weight for min-max normalized vector retrieval score",
    )
    discover_max_cv_text_chars: int = Field(
        default=120_000,
        ge=4096,
        description="Max characters passed to the CV skills agent",
    )
    discover_retrieval_limit_cvs: int = Field(
        default=40,
        ge=1,
        description="Internal top_k_cvs (k′) before final shortlist",
    )
    discover_retrieval_limit_chunks: int = Field(
        default=120,
        ge=1,
        description="Internal top_k_chunks before collapse",
    )
    discover_max_cvs_to_score: int = Field(
        default=25,
        ge=1,
        description="Cap on CVs processed by LLM agents per request (cost control)",
    )
    discover_llm_timeout_s: float = Field(
        default=120.0,
        ge=5.0,
        description="Per agent run timeout (seconds)",
    )
    discover_llm_concurrency: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Max parallel per-CV LLM pipelines",
    )

    cors_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        description=(
            "Comma-separated browser origins for CORS. "
            "If empty (e.g. CORS_ORIGINS= in .env), dev defaults for Vite are applied in code."
        ),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
