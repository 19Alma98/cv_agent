from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from qdrant_client import QdrantClient

from cv_agent.api.routes.health import get_qdrant
from cv_agent.clients.qdrant import qdrant_reachable
from cv_agent.config import Settings, get_settings
from cv_agent.retrieval.models import RetrievalResult, SearchRequest
from cv_agent.retrieval.search import RetrievalServiceError, search_cvs

router = APIRouter(tags=["retrieval"])


@router.post(
    "/internal/retrieve",
    response_model=RetrievalResult,
    responses={
        400: {"description": "Invalid query or limits"},
        503: {"description": "Qdrant or embedding provider unavailable"},
    },
)
def internal_retrieve(
    body: SearchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[QdrantClient, Depends(get_qdrant)],
) -> RetrievalResult:
    q = body.query.strip()
    if not q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query must be non-empty",
        )

    if body.limit_cvs > settings.search_max_limit_cvs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"limit_cvs must be <= {settings.search_max_limit_cvs} "
                f"(got {body.limit_cvs})"
            ),
        )
    if body.limit_chunks > settings.search_max_limit_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"limit_chunks must be <= {settings.search_max_limit_chunks} "
                f"(got {body.limit_chunks})"
            ),
        )

    ok, err = qdrant_reachable(client)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=err or "qdrant_unreachable",
        )

    try:
        return search_cvs(
            q,
            settings,
            client,
            top_k_cvs=body.limit_cvs,
            top_k_chunks=body.limit_chunks,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except RetrievalServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e


@router.post("/search", response_model=RetrievalResult, include_in_schema=True)
def search_alias(
    body: SearchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[QdrantClient, Depends(get_qdrant)],
) -> RetrievalResult:
    """Same behavior as ``POST /internal/retrieve`` (convenience alias)."""
    return internal_retrieve(body, settings, client)
