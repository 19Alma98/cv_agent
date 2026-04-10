from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from qdrant_client import QdrantClient

from cv_agent.api.routes.health import router as health_router
from cv_agent.api.routes.retrieve import router as retrieve_router
from cv_agent.clients.qdrant import get_client
from cv_agent.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    client: QdrantClient = get_client(settings)
    app.state.qdrant_client = client
    try:
        yield
    finally:
        client.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="CV Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(retrieve_router)
    return app


app = create_app()
