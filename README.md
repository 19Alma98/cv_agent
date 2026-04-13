# CV Agent

Python service for the CV discovery pipeline: Qdrant-backed indexing and retrieval, **Microsoft Agent Framework** workflows, and a **FastAPI** surface. A **React + Vite** UI lives under `frontend/` to call `/discover` and browse reports.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependencies
- Node.js 20+ (for the frontend only)

## Backend setup

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
| `QDRANT_COLLECTION_NAME` | No | CV chunk collection name (default `cv_chunks`) |
| `EMBEDDING_PROVIDER` | No | `openai` (default), `azure_openai` (resource + API key), or `azure_foundry` (project + Entra ID) |
| `AZURE_AI_PROJECT_ENDPOINT` | No‡ | Foundry **project** URL when using `azure_foundry` (not `*.openai.azure.com`) |
| `EMBEDDING_API_KEY` | No* | API key for `openai` / `azure_openai` (ignored for `azure_foundry`) |
| `EMBEDDING_BASE_URL` | No† | `openai`: optional API base. `azure_openai`: resource root |
| `EMBEDDING_API_VERSION` | No | `azure_openai` only; defaults to `2024-02-01` if unset |
| `EMBEDDING_MODEL` | No* | Model or **deployment** name (Foundry: deployment name in the project) |
| `EMBEDDING_VECTOR_SIZE` | No | Vector dimension for Qdrant (default **3072**; must match the deployed model) |
| `LLM_PROVIDER` | No | `openai`, `azure_openai`, or `azure_foundry` (discover phase) |
| `LLM_API_KEY` | No* | Chat API key (not used when `LLM_PROVIDER=azure_foundry`) |
| `LLM_BASE_URL` | No | `openai` / `azure_openai` only |
| `LLM_API_VERSION` | No | `azure_openai` only |
| `LLM_MODEL` | No* | Model or chat **deployment** name |
| `CV_INGEST_ROOT` | No | Directory with CV files or `manifest.json` for `cv-reindex` |
| `CORS_ORIGINS` | No | Comma-separated browser origins. If unset or empty, dev defaults include Vite on `:5173` |

\*Required when you enable ingestion or LLM features (except Foundry uses Entra instead of API keys).  
†Required for `azure_openai` embeddings: `EMBEDDING_BASE_URL` on `*.openai.azure.com`.  
‡Required for `azure_foundry`: set `AZURE_AI_PROJECT_ENDPOINT` and authenticate with `DefaultAzureCredential` (e.g. `az login`, managed identity, or env-based service principal).

Optional **discover** tuning (see `.env.example`): `DISCOVER_W_COVERAGE`, `DISCOVER_W_VECTOR`, `DISCOVER_MAX_CV_TEXT_CHARS`, `DISCOVER_RETRIEVAL_LIMIT_CVS`, `DISCOVER_RETRIEVAL_LIMIT_CHUNKS`, `DISCOVER_MAX_CVS_TO_SCORE`, `DISCOVER_LLM_TIMEOUT_S`, `DISCOVER_LLM_CONCURRENCY`.

`pydantic-settings` loads `.env` in development if `python-dotenv` is installed (included in the dev dependency group).

## Qdrant (local)

Start Qdrant with Docker Compose:

```bash
docker compose up -d qdrant
```

## Index CVs into Qdrant

Point `CV_INGEST_ROOT` (or pass `--root`) at your source tree and configure embeddings, then:

```bash
uv run cv-reindex --help
```

The job extracts text (PDF/text), normalizes, chunks, embeds, and upserts into the configured collection.

## Run the API

```bash
export QDRANT_URL=http://localhost:6333
uv run cv-agent-serve
```

Or with uvicorn directly:

```bash
uv run uvicorn cv_agent.main:create_app --factory --host 127.0.0.1 --port 8000
```

Host, port, and reload can be set with `CV_AGENT_HOST`, `CV_AGENT_PORT`, and `CV_AGENT_RELOAD` (see `.env.example`).

### HTTP routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | JSON with `status`, `qdrant` (`ok` / `error`), `version`, and optional `message`. Returns **503** when Qdrant is unreachable. |
| `POST` | `/search` | Vector search over CVs; same contract as `POST /internal/retrieve`. |
| `POST` | `/internal/retrieve` | Internal retrieval (`query`, per-CV / per-chunk limits). |
| `POST` | `/discover` | Full discovery: retrieval plus agents on JD/CVs, ranking, and skill match summaries. Needs Qdrant, embeddings, and LLM. **400** if both `query` and `job_description` are empty; **503** on service failures. |

## Frontend (UI)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

- `VITE_API_BASE_URL` — API base URL (default `http://127.0.0.1:8000` if unset).
- If `CORS_ORIGINS` is missing or empty, the API still allows the default Vite dev origins (`127.0.0.1` and `localhost` on port `5173`).

## Microsoft Agent Framework

The **discover** path uses the **agent-framework** and **agent-framework-openai** packages (PyPI): agents for job-description skills, per-CV skills, and matching/readable summaries, orchestrated with configurable timeouts and concurrency (`DISCOVER_LLM_*`). Upstream retrieval uses Qdrant and your configured embedding provider; the composite score blends vector similarity and skill coverage (`DISCOVER_W_*`).

When adding agent behavior, prefer the framework’s **tools** and **workflows** over one-off scripts so orchestration stays consistent and maintainable.
