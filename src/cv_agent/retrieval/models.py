from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkHit(BaseModel):
    chunk_index: int
    score: float
    text: str
    source: str | None = None


class CvHit(BaseModel):
    cv_id: str
    score: float
    chunks: list[ChunkHit]


class RetrievalMeta(BaseModel):
    embedding_model_id: str
    k_prime: int
    k: int


class RetrievalResult(BaseModel):
    query: str
    cvs: list[CvHit]
    meta: RetrievalMeta


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit_cvs: int = Field(default=20, ge=1)
    limit_chunks: int = Field(default=80, ge=1)
