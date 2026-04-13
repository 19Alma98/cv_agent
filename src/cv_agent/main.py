from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

from cv_agent.api.routes.discover import router as discover_router
from cv_agent.api.routes.health import router as health_router
from cv_agent.api.routes.retrieve import router as retrieve_router
from cv_agent.clients.qdrant import get_client
from cv_agent.config import get_settings

# Used when CORS_ORIGINS is unset or empty (common in local .env with `CORS_ORIGINS=`).
_DEFAULT_VITE_DEV_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


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
    settings = get_settings()
    app = FastAPI(
        title="CV Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if not origins:
        origins = list(_DEFAULT_VITE_DEV_ORIGINS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(retrieve_router)
    app.include_router(discover_router)
    return app


app = create_app()
