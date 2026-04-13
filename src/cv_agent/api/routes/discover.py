from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from qdrant_client import QdrantClient

from cv_agent.api.routes.health import get_qdrant
from cv_agent.clients.qdrant import qdrant_reachable
from cv_agent.config import Settings, get_settings
from cv_agent.discovery.schemas import DiscoverRequest, DiscoverResponse
from cv_agent.discovery.workflow import DiscoverError, run_discover

logger = logging.getLogger(__name__)

router = APIRouter(tags=["discover"])


@router.post(
    "/discover",
    response_model=DiscoverResponse,
    responses={
        400: {"description": "Invalid request (empty query and job description)"},
        503: {"description": "Qdrant, embedding, or LLM unavailable"},
    },
)
async def discover(
    body: DiscoverRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[QdrantClient, Depends(get_qdrant)],
) -> DiscoverResponse:
    q = body.query.strip()
    jd = (body.job_description or "").strip()
    if not q and not jd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a non-empty query and/or job_description",
        )

    if body.top_k > settings.search_max_limit_cvs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"top_k must be <= {settings.search_max_limit_cvs} (got {body.top_k})",
        )

    ok, err = qdrant_reachable(client)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=err or "qdrant_unreachable",
        )

    try:
        return await run_discover(body, settings, client)
    except DiscoverError as e:
        logger.warning("discover failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
