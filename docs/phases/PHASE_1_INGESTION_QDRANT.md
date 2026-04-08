# Phase 1 — Ingestion + Qdrant

**Parent document:** [CV discovery pipeline](../CV_DISCOVERY_PIPELINE.md) · §4, §8 Phase 1  
**Prerequisites:** [Phase 0 — Foundations](./PHASE_0_FOUNDATIONS.md) complete.

This phase implements the **offline path**: read CVs from your source of truth, normalize text, **chunk**, **embed**, and **upsert** into Qdrant with consistent **payloads** so Phase 2 retrieval can collapse by `cv_id` and attach evidence spans.

---

## 1.1 Purpose and outcomes

**Goal:** Every CV (or updated CV) in scope is represented in Qdrant as one or more points in a collection (e.g. `cv_chunks`), each with:

- A **dense vector** from the chosen embedding model.
- **Payload** fields agreed for filtering and grouping (minimum: `cv_id`, `chunk_index`; recommended extras per parent [§4.1](../CV_DISCOVERY_PIPELINE.md)).

**Phase complete when:**

1. Collection exists with correct **vector size** and distance metric (typically **Cosine** for normalized embeddings; follow your embedding vendor’s recommendation).
2. A **batch job or CLI** can ingest all CVs or **incrementally** reindex “since” a timestamp or version.
3. Ingestion is **idempotent enough** for v1: re-running upsert for the same logical chunk does not duplicate points (use deterministic point IDs — see §1.6).
4. **Ingestion metadata** (parser version, embedding model id, chunk params) is recorded somewhere queryable (payload field, separate table, or log aggregate) for debugging and full re-embeds.

---

## 1.2 Data flow (concrete steps)

1. **Fetch** CV record from your DB (or storage): raw file (PDF/HTML/DOCX) or pre-extracted text.
2. **Extract text** if needed:
   - PDF: library such as `pypdf`, `pdfplumber`, or a dedicated service; handle failures explicitly (empty text → log + skip or quarantine).
   - HTML: strip tags, preserve rough structure if useful for chunking (e.g. headings).
3. **Normalize**:
   - Unicode NFC, trim whitespace, optional line-ending normalization.
   - **PII policy** (parent [§7](../CV_DISCOVERY_PIPELINE.md)): decide what is redacted before embedding and what is never logged.
4. **Chunk** (parent [§4.1](../CV_DISCOVERY_PIPELINE.md)):
   - Target **512–1024 tokens** (or character approximation if you use char counts — document the choice).
   - **Overlap** (e.g. 10–20%) to avoid cutting sentences across chunk boundaries.
   - Optional: **section-aware** chunking (split on “Experience”, “Education”) if your CVs have predictable structure; fallback to sliding window.
5. **Embed** each chunk in batches (respect provider rate limits and max batch size).
6. **Upsert** to Qdrant with payload + **stable point id**.

---

## 1.3 Qdrant collection schema

**Collection name (v1):** e.g. `cv_chunks` (parent [§4.2](../CV_DISCOVERY_PIPELINE.md)).

**Vector:**

- **Size:** must match embedding model output (e.g. 1536, 3072, 768).
- **Distance:** Cosine is common for text embeddings; verify against model docs.

**Payload fields (minimum viable):**

| Field | Type (conceptual) | Required | Notes |
|--------|-------------------|----------|--------|
| `cv_id` | string or integer as string | Yes | Groups chunks for collapse in Phase 2 |
| `chunk_index` | integer | Yes | Order within CV |
| `text` | string | Strongly recommended | Store chunk text in payload for scoring agents without a second DB round-trip for v1 |
| `source` | string | Optional | e.g. `experience`, `summary`, `skills` |
| `ingestion_version` | string | Recommended | e.g. `parser-1.0_embed-text-embedding-3-large_512-128ov` |

**Future / if extractable reliably:**

- `last_updated` (ISO date), `location`, `primary_skills[]`, `years_experience_*` — enables filters ([§5.2](../CV_DISCOVERY_PIPELINE.md)).

**Indexes:** Create payload indexes for fields you filter on (`cv_id` if you ever filter by CV; `last_updated` for range queries). For v1 vector-only search, payload indexes may be minimal.

---

## 1.4 Point IDs (idempotency)

**Problem:** Naive random UUIDs create duplicates on re-run.

**Recommended:** Deterministic id from content and version, for example:

- `point_id = hash(f"{ingestion_version}:{cv_id}:{chunk_index}")` mapped to UUID, **or**
- Use Qdrant’s support for string UUIDs derived from a stable hash.

**On CV update:** Either delete all points for `cv_id` then re-upsert, or upsert with the same ids so chunks are replaced. Document the chosen strategy.

---

## 1.5 CLI / job: `reindex`

**Interface sketch:**

```bash
uv run python -m cv_agent.jobs.reindex --since 2025-01-01T00:00:00Z
uv run python -m cv_agent.jobs.reindex --cv-id <id>
uv run python -m cv_agent.jobs.reindex --full
```

**Behavior:**

- **`--since`:** Select CVs whose `updated_at` (or equivalent) is ≥ threshold. For deleted CVs, define policy (remove from Qdrant in a separate `cleanup` job if needed).
- **`--cv-id`:** Single-CV refresh (support debugging).
- **`--full`:** Full rebuild; optionally recreate collection or batch-delete by filter before bulk upsert.

**Operational notes:**

- **Batch size:** Tune embedding API batches and Qdrant upsert batches (e.g. 64–256 points per request depending on payload size).
- **Retries:** Transient network errors on embed and upsert should retry with backoff.
- **Progress:** Log counts processed, failed, skipped; exit non-zero on hard failures if you want CI to catch breakage.

Register the CLI via `pyproject.toml`:

```toml
[project.scripts]
cv-reindex = "cv_agent.jobs.reindex:main"
```

---

## 1.6 Embedding model consistency

**Rule:** The **same model** (and preprocessing) must be used for **documents (CV chunks)** and **queries** in Phase 2 ([§10.2](../CV_DISCOVERY_PIPELINE.md)).

**Document in config:**

- Model name and version / deployment id.
- Expected vector dimension.
- Any provider-specific instructions (e.g. “replace newlines with space” for some OpenAI models).

Store `embedding_model_id` in payload or ingestion logs so you can detect mixed-model disasters after a bad deploy.

---

## 1.7 Testing and acceptance

**Unit tests:**

- Chunker: given fixed input text, expected number of chunks and overlap behavior.
- Normalization: edge cases (empty, very long, unicode).

**Integration tests (optional CI with Qdrant service):**

- Upsert a handful of synthetic points; `scroll` or `search` with a trivial vector (or random) might be flaky — better: **known embedding** for a fixed string if you can cache vectors, or call real embed API in a gated job.

**Manual acceptance:**

1. Run ingestion on 2–3 real CVs.
2. In Qdrant dashboard or via client: verify point count ≥ chunk count, payloads contain `cv_id` and `text`.
3. Run a simple `search` with a query embedding for a phrase that appears in one CV; verify relevant chunk ranks high.

---

## 1.8 Pitfalls (from parent doc)

- **Whole-document single vector** — hurts explainability; prefer chunks ([§4.1](../CV_DISCOVERY_PIPELINE.md)).
- **Mixed embedding models** in one collection — invalid or misleading similarity.
- **PDF extraction quality** — garbage in → garbage embeddings; monitor empty or ultra-short extractions.
- **Token vs character chunking** — be consistent with how you estimate length vs what the embed API counts.

---

## 1.9 Checklist

- [ ] Collection created with correct dimension and distance.
- [ ] Text extraction + normalize + chunk pipeline implemented.
- [ ] Embed batching + upsert with full payload.
- [ ] Stable point ids or delete-and-replace strategy documented.
- [ ] `reindex` (or equivalent) supports `--since` and manual single-CV path.
- [ ] `ingestion_version` (or equivalent) recorded per point or per batch.
- [ ] README: how to run full and incremental index.

---

## 1.10 Handoff to Phase 2

Phase 2 needs:

- Populated `cv_chunks` (or whatever you named it) with **queryable vectors** and **`cv_id` on every point**.
- Shared **embedding function** in code used by both ingestion and query path (same model, same preprocessing).

Next: [Phase 2 — Retrieval only](./PHASE_2_RETRIEVAL_ONLY.md).
