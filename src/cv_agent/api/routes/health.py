from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

from cv_agent.clients.qdrant import qdrant_reachable


def _app_version() -> str:
    try:
        return version("cv-agent")
    except PackageNotFoundError:
        return "0.0.0"


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    qdrant: Literal["ok", "error", "down"] = "ok"
    version: str = Field(default_factory=_app_version)
    message: str | None = None


router = APIRouter(tags=["health"])


def get_qdrant(request: Request) -> QdrantClient:
    client = getattr(request.app.state, "qdrant_client", None)
    if client is None:
        raise RuntimeError("Qdrant client not initialized on app.state")
    return client


@router.get("/health", response_model=HealthResponse)
def health(
    response: Response,
    client: Annotated[QdrantClient, Depends(get_qdrant)],
) -> HealthResponse:
    """
    Liveness/readiness-style probe including Qdrant connectivity.
    Returns 503 when Qdrant cannot be reached (or returns an HTTP error).
    """
    ok, err = qdrant_reachable(client)
    if ok:
        return HealthResponse(status="ok", qdrant="ok", message=None)

    response.status_code = 503
    return HealthResponse(
        status="degraded",
        qdrant="error",
        message=err,
    )
