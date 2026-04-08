from functools import lru_cache

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
    embedding_base_url: str = Field(
        default="",
        description="Optional base URL (e.g. Azure OpenAI or proxy)",
    )
    embedding_model: str = Field(
        default="",
        description="Embedding model id / deployment name",
    )

    llm_api_key: str = Field(default="", description="API key for chat model")
    llm_base_url: str = Field(default="", description="Optional LLM API base URL")
    llm_model: str = Field(default="", description="Chat model id / deployment name")


@lru_cache
def get_settings() -> Settings:
    return Settings()
