from __future__ import annotations

import importlib.metadata
import json

import agent_framework as _agent_framework_pkg

if not hasattr(_agent_framework_pkg, "__version__"):
    try:
        _af_ver = importlib.metadata.version("agent-framework")
    except importlib.metadata.PackageNotFoundError:
        _af_ver = "1.0.0"
    setattr(_agent_framework_pkg, "__version__", _af_ver)

from agent_framework._middleware import FunctionInvocationContext
from agent_framework._tools import FunctionTool
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

from cv_agent.config import Settings
from cv_agent.retrieval.cv_document import fetch_cv_document_text
from cv_agent.retrieval.search import search_cvs


class SearchCvsToolInput(BaseModel):
    query: str = Field(..., description="Semantic search query for CVs")
    top_k_cvs: int = Field(default=20, ge=1, le=200, description="Max distinct CVs")
    top_k_chunks: int = Field(default=80, ge=1, le=500, description="Max chunks before collapse")


def _search_cvs_impl(
    query: str,
    top_k_cvs: int,
    top_k_chunks: int,
    ctx: FunctionInvocationContext,
) -> str:
    settings: Settings = ctx.kwargs["settings"]
    client: QdrantClient = ctx.kwargs["qdrant"]
    result = search_cvs(
        query,
        settings,
        client,
        top_k_cvs=top_k_cvs,
        top_k_chunks=top_k_chunks,
    )
    return result.model_dump_json()


class GetCvDocumentToolInput(BaseModel):
    cv_id: str = Field(..., description="CV identifier")


def _get_cv_document_impl(cv_id: str, ctx: FunctionInvocationContext) -> str:
    settings: Settings = ctx.kwargs["settings"]
    client: QdrantClient = ctx.kwargs["qdrant"]
    max_chars: int = int(ctx.kwargs.get("discover_max_cv_text_chars", 120_000))
    doc = fetch_cv_document_text(client, settings, cv_id, max_chars=max_chars)
    return json.dumps({
        "cv_id": doc.cv_id,
        "text": doc.text,
        "truncated": doc.truncated,
        "chunk_count": doc.chunk_count,
    })


def build_retrieval_function_tools() -> list[FunctionTool]:
    """Microsoft Agent Framework tools wrapping Phase 2 retrieval and CV text load."""
    return [
        FunctionTool(
            name="search_cvs",
            description=(
                "Embed the query and search Qdrant for CV chunks; results collapsed by cv_id. "
                "Use for building a working set of candidates."
            ),
            func=_search_cvs_impl,
            input_model=SearchCvsToolInput,
        ),
        FunctionTool(
            name="get_cv_document",
            description=(
                "Load full CV text from stored chunks for a cv_id, ordered by chunk_index, "
                "truncated to a server max length if needed."
            ),
            func=_get_cv_document_impl,
            input_model=GetCvDocumentToolInput,
        ),
    ]
