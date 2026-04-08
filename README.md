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
| `EMBEDDING_PROVIDER` | No | `openai` (default), `azure_openai` (resource + API key), or `azure_foundry` (project + Entra ID) |
| `AZURE_AI_PROJECT_ENDPOINT` | No‡ | Foundry **project** URL when using `azure_foundry` (not `*.openai.azure.com`) |
| `EMBEDDING_API_KEY` | No* | API key for `openai` / `azure_openai` (ignored for `azure_foundry`) |
| `EMBEDDING_BASE_URL` | No† | `openai`: optional API base. `azure_openai`: resource root |
| `EMBEDDING_API_VERSION` | No | `azure_openai` only; defaults to `2024-02-01` if unset |
| `EMBEDDING_MODEL` | No* | Model or **deployment** name (Foundry: deployment name in the project) |
| `EMBEDDING_VECTOR_SIZE` | No | Vector dimension for Qdrant (default `1536`; must match the deployed model) |
| `LLM_PROVIDER` | No | `openai`, `azure_openai`, or `azure_foundry` (Phase 3+; Foundry uses SDK + Entra) |
| `LLM_API_KEY` | No* | Chat API key (not used when `LLM_PROVIDER=azure_foundry`) |
| `LLM_BASE_URL` | No | `openai` / `azure_openai` only |
| `LLM_API_VERSION` | No | `azure_openai` only |
| `LLM_MODEL` | No* | Model or chat **deployment** name |

\*Required when you enable ingestion or agent features in later phases (except Foundry uses Entra instead of API keys).  
†Required for `azure_openai` embeddings: `EMBEDDING_BASE_URL` on `*.openai.azure.com`.  
‡Required for `azure_foundry`: set `AZURE_AI_PROJECT_ENDPOINT` and authenticate with `DefaultAzureCredential` (e.g. `az login`, managed identity, or env-based service principal).

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
