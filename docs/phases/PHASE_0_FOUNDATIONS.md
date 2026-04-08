# Phase 0 — Foundations

**Parent document:** [CV discovery pipeline](../CV_DISCOVERY_PIPELINE.md) · §8 Phase 0

This phase establishes the Python project, dependencies, configuration discipline, and a running Qdrant instance so later phases can focus on domain logic rather than environment setup.

---

## 0.1 Purpose and outcomes

**Goal:** A reproducible local (and CI-friendly) baseline where:

- Dependencies are pinned and installed via **`uv`** (per project convention).
- Configuration is **environment-driven** (no secrets in code).
- **Qdrant** is reachable from the application code with a smoke test.
- A minimal **HTTP service skeleton** exists (e.g. FastAPI) with `/health` that can be extended in Phase 2 and Phase 3.

**Phase complete when:**

1. `uv sync` (or equivalent) installs all declared dependencies without conflict.
2. Qdrant runs (Docker Compose or managed) and the app can connect using env vars.
3. `/health` returns JSON including at least `status` and a boolean or message for Qdrant connectivity (actual check can be a simple `get_collections` or ping).
4. A short **README section** or inline comment documents required env vars (no need for a separate architecture doc unless you prefer one).

---

## 0.2 Dependencies (recommended)

Align with the parent pipeline ([§3](../CV_DISCOVERY_PIPELINE.md), [§6](../CV_DISCOVERY_PIPELINE.md), [§7](../CV_DISCOVERY_PIPELINE.md)):

| Package / area | Role |
|----------------|------|
| **Microsoft Agent Framework** (`agent-framework` on PyPI) | Agents, tools, workflows (Phase 3). Install now so import paths and versions are stable. |
| **`qdrant-client`** | Talk to Qdrant from Python (Phases 1–2). |
| **Embedding SDK** | Depends on chosen model (e.g. OpenAI, Azure OpenAI, local `sentence-transformers`). Pick one for v1 and document it. |
| **FastAPI** (+ **uvicorn**) | HTTP API for `/health`, later `/discover` and ingest hooks. |
| **Pydantic** (v2) | Settings and JSON schemas; often pulled in by FastAPI. |
| **`pydantic-settings`** | `BaseSettings` for typed env config. |
| **HTTP client** (`httpx`) | Useful for embedding APIs and tests. |

**Optional but useful early:**

- **`python-dotenv`** — load `.env` in dev only; production should use real env injection.
- **Structured logging** — `structlog` or stdlib `logging` with JSON formatter for Phase 4.

**Development:**

- **`pytest`**, **`pytest-asyncio`** — async routes and clients.
- **`ruff`** (or similar) — lint/format if the team adopts it.

Add these to `pyproject.toml` under `[project] dependencies` and lock with `uv lock` / `uv sync`.

---

## 0.3 Project layout (suggested)

You can evolve this, but a clear structure speeds up Phases 1–3:

```text
cv_agent/
  pyproject.toml
  README.md
  .env.example          # no secrets; list all keys with placeholder values
  docker-compose.yml    # optional: Qdrant (+ optional admin UI)
  src/
    cv_agent/
      __init__.py
      config.py         # Pydantic Settings: QDRANT_URL, QDRANT_API_KEY, etc.
      main.py           # FastAPI app factory + lifespan (Qdrant client init)
      api/
        routes/
          health.py
      clients/
        qdrant.py       # thin wrapper: get_client(), health_check()
```

Keep **ingestion** and **workflow** modules empty or stubbed until Phase 1 and Phase 3; Phase 0 only needs config + Qdrant client + health route.

---

## 0.4 Configuration via environment

Define a **single** settings object (e.g. `Settings` in `config.py`) loaded from env. Minimum variables:

| Variable | Purpose |
|----------|---------|
| `QDRANT_URL` | Base URL, e.g. `http://localhost:6333` |
| `QDRANT_API_KEY` | Empty for local dev if Qdrant has no auth; set for cloud/managed |
| `EMBEDDING_*` | Prefix for whatever your embedding provider needs (API key, base URL, deployment name) |
| `LLM_*` | Same for the chat model used in Phase 3 (can be added in Phase 3 if you prefer) |

**Rules:**

- Never commit `.env`; commit **`.env.example`** with dummy values and comments.
- Fail fast on startup if required vars are missing (Pydantic `validation_error` is enough).

---

## 0.5 Qdrant: Docker Compose (example)

A minimal `docker-compose.yml` service:

- Image: official Qdrant image (pin a version tag, not `latest`, for reproducibility).
- Ports: `6333` (REST), `6334` (gRPC) as needed.
- Optional: volume for persistence across restarts.

**Smoke test (manual or pytest):**

1. Start Compose.
2. From Python, create `QdrantClient(url=settings.qdrant_url, api_key=...)`.
3. Call `get_collections()` and assert no exception (or expect a specific error only when Qdrant is down).

Document in README: how to start Qdrant and run the app.

---

## 0.6 FastAPI `/health` contract (v0)

**Purpose:** Operations and Phase 2+ callers need a stable liveness/readiness probe.

**Suggested response shape (JSON):**

```json
{
  "status": "ok",
  "qdrant": "ok",
  "version": "0.1.0"
}
```

If Qdrant is unreachable:

- Either return `503` with `qdrant: "error"` and a safe message, or keep `200` with `qdrant: "down"` depending on your orchestration policy. **Kubernetes:** typically use separate `/live` vs `/ready`; for Phase 0, one endpoint is enough if documented.

---

## 0.7 Microsoft Agent Framework (install only)

Phase 0 does **not** need a working agent yet. Do verify:

- Package imports successfully at the chosen version.
- Skim the official repo/docs for **workflow** and **tool** patterns you will use in Phase 3.

This avoids a late dependency surprise when wiring `/discover`.

---

## 0.8 Open decisions to revisit

From parent doc [§10](../CV_DISCOVERY_PIPELINE.md):

- **Embedding model** and provider — lock before Phase 1 ends (dimension must match Qdrant collection).
- **Source of truth** for raw CV bytes — affects Phase 1 fetch code only, but naming env vars early (`CV_DB_URL`, `S3_BUCKET`, etc.) helps.

---

## 0.9 Checklist (copy for PRs)

- [x] `pyproject.toml` lists core deps; `uv sync` works.
- [x] `.env.example` documents all required variables.
- [x] Qdrant runs locally via documented command.
- [x] Application reads config from env; no secrets in repo.
- [x] `/health` (or equivalent) performs Qdrant connectivity check.

---

## 0.10 Handoff to Phase 1

Phase 1 needs:

- A **Qdrant client** available from application code.
- **Known embedding model** and **vector size** (create collection in Phase 1 using that dimension).
- A place to put **ingestion scripts** (CLI entry point in `pyproject.toml` `[project.scripts]` recommended).

Next: [Phase 1 — Ingestion + Qdrant](./PHASE_1_INGESTION_QDRANT.md).
