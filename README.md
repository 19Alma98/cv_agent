# CV Agent

Python service for the CV discovery pipeline: Qdrant-backed retrieval, Microsoft Agent Framework workflows (later phases), and a FastAPI surface.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependencies

## Setup

```bash
uv sync --all-groups
cp .env.example .env
# Set at least QDRANT_URL (see Environment variables)
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `QDRANT_URL` | Yes | Qdrant REST base URL (e.g. `http://localhost:6333`) |
| `QDRANT_API_KEY` | No | API key for managed Qdrant; omit or empty locally |
| `EMBEDDING_API_KEY` | No* | Embedding provider API key (Phase 1+) |
| `EMBEDDING_BASE_URL` | No | Optional base URL for embeddings |
| `EMBEDDING_MODEL` | No* | Model or deployment id |
| `LLM_API_KEY` | No* | Chat model API key (Phase 3) |
| `LLM_BASE_URL` | No | Optional LLM API base URL |
| `LLM_MODEL` | No* | Chat model id |

\*Required when you enable ingestion or agent features in later phases.

`pydantic-settings` loads `.env` in development if `python-dotenv` is installed (included in the dev dependency group).

## Qdrant (local)

Start Qdrant with Docker Compose:

```bash
docker compose up -d qdrant
```

## Run the API

```bash
export QDRANT_URL=http://localhost:6333
uv run cv-agent-serve
```

Or with uvicorn directly:

```bash
uv run uvicorn cv_agent.main:create_app --factory --host 127.0.0.1 --port 8000
```

- **GET `/health`** — JSON with `status`, `qdrant` (`ok` / `error`), `version`, and optional `message`. Returns **503** when Qdrant is unreachable.

## Microsoft Agent Framework
