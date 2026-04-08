# Phase 2 — Retrieval only

**Parent document:** [CV discovery pipeline](../CV_DISCOVERY_PIPELINE.md) · §5, §6.2, §8 Phase 2  
**Prerequisites:** [Phase 1 — Ingestion + Qdrant](./PHASE_1_INGESTION_QDRANT.md) complete (collection populated).

This phase implements **semantic recall** without LLM agents: embed the user query, search Qdrant, **collapse chunk hits to unique CVs**, and expose results via a **minimal HTTP API** (and/or an internal Python function that Phase 3 will wrap as a tool).

---

## 2.1 Purpose and outcomes

**Goal:** Given a natural language string (HR query or raw keywords), return:

- **Top `k` CV IDs** after collapsing chunk-level hits.
- For each CV, the **best supporting chunks** (text + score + metadata) for downstream scoring and UI.

**Phase complete when:**

1. `search_cvs` (name per parent [§6.2](../CV_DISCOVERY_PIPELINE.md)) is implemented as a **pure retrieval** module: no criteria agent, no LLM reranking.
2. **Collapse-by-`cv_id`** matches the strategy documented in [§5.1](../CV_DISCOVERY_PIPELINE.md).
3. **POST** (or GET) endpoint returns JSON with CV ids, aggregated scores, and chunks; stable enough for Phase 3 to consume unchanged or with thin adapters.
4. **Limits** enforced: max `k`, max `k_prime` (chunk hits before collapse) to control cost and latency ([§1.2 caveat 3](../CV_DISCOVERY_PIPELINE.md), [§10.4](../CV_DISCOVERY_PIPELINE.md)).

---

## 2.2 API surface (minimal)

**Suggested:** `POST /search` or `POST /internal/retrieve` (if you reserve `/discover` for Phase 3).

**Request body (example):**

```json
{
  "query": "Senior Java developer with Spring and microservices experience",
  "limit_cvs": 20,
  "limit_chunks": 80
}
```

**Semantics:**

- `limit_chunks` → Qdrant `limit` **k′** (e.g. 50–100): max **points** (chunks) returned from vector search before collapse.
- `limit_cvs` → **k**: max distinct `cv_id` values after collapse.

**Response body (example):**

```json
{
  "query": "Senior Java developer ...",
  "cvs": [
    {
      "cv_id": "uuid-123",
      "score": 0.82,
      "chunks": [
        {
          "chunk_index": 3,
          "score": 0.85,
          "text": "...",
          "source": "experience"
        }
      ]
    }
  ],
  "meta": {
    "embedding_model_id": "text-embedding-3-large",
    "k_prime": 80,
    "k": 20
  }
}
```

**Errors:**

- `400` for missing/empty query or out-of-range limits.
- `503` if Qdrant or embedding provider unavailable (align with Phase 0 health policy).

---

## 2.3 Embedding the query

Use the **identical** embedding pipeline as Phase 1:

- Same model, API, preprocessing.
- Single vector per query for v1 (parent flow allows **multiple sub-queries** later from the criteria agent — Phase 3).

**Implementation detail:** Centralize `embed_query(text: str) -> list[float]` (or numpy array) in a small module shared with ingestion.

---

## 2.4 Qdrant search

**Call:** `client.search(collection_name=..., query_vector=..., limit=k_prime, with_payload=True)`.

**Filters (optional in Phase 2):**

- If payloads include `last_updated`, `location`, etc., expose optional filter parameters on the API **only if** you already ingest those fields; otherwise defer to Phase 3 or a later iteration ([§5.2](../CV_DISCOVERY_PIPELINE.md)).

**Score:** Qdrant returns a similarity score per point; keep the raw score on each chunk for debugging.

---

## 2.5 Collapse-by-`cv_id` algorithm

**Input:** Ordered list of chunk hits (descending by score).  
**Output:** Top `k` CVs, each with an **aggregate score** and **selected chunks**.

**Recommended v1 aggregation:**

1. Group all hits by `payload["cv_id"]`.
2. **CV-level score** = **max** chunk score for that CV (simple, interpretable “best matching span”).
3. Sort CVs by that aggregate descending.
4. Take top `k` CVs.

**Chunks to return per CV:**

- Keep the **top N chunks** per CV by chunk score (e.g. N = 3–5) for context in Phase 3 agents ([§5.1](../CV_DISCOVERY_PIPELINE.md)).
- Deduplicate by `chunk_index` if the same chunk appears twice (should not happen if points are unique).

**Alternatives** (document if you choose one):

- **Weighted mean** of top 3 chunk scores.
- **Sum** of scores (biased toward long CVs with many chunks — usually avoid).

---

## 2.6 The `search_cvs` tool shape (for Phase 3)

Even in Phase 2, implement retrieval as a **callable** the agent framework can register later:

```text
search_cvs(
  query: str,
  top_k_cvs: int = 20,
  top_k_chunks: int = 80,
  filters: dict | None = None,
) -> RetrievalResult
```

Where `RetrievalResult` is a Pydantic model mirroring the JSON response. Phase 3 wraps this in the framework’s tool decorator / function schema.

---

## 2.7 Performance and limits

- **k′** large enough to recall relevant CVs that only appear in “weak” chunks; **k** small enough for downstream LLM cost ([§1.2](../CV_DISCOVERY_PIPELINE.md): retrieve top 50–100 chunks, present top 10–20 CVs to heavy agents — tune per budget).
- **Timeouts:** Set HTTP client timeouts for embedding and Qdrant.
- **Caching:** Optional later; not required in Phase 2.

---

## 2.8 Testing

**Unit tests:**

- Collapse logic: synthetic hits with duplicate `cv_id`, verify ordering and top-N chunks per CV.
- Validation: reject `limit_cvs > MAX` if you cap for safety.

**Integration tests:**

- Seed Qdrant with known chunks (from Phase 1 test data); query with a phrase from one chunk; assert that CV appears in top results.

---

## 2.9 Pitfalls

- **Returning only chunk IDs** without text forces Phase 3 to hit DB for every snippet — slow. Prefer payload `text` if size allows.
- **Ignoring score ties** — stable tie-break (secondary sort on `cv_id`) helps regression tests.
- **Different embedding model** than ingestion — silent quality collapse.

---

## 2.10 Checklist

- [ ] Query embedding uses same model as ingestion.
- [ ] Qdrant search with configurable k′.
- [ ] Collapse-by-`cv_id` with documented aggregate rule.
- [ ] Per-CV top chunk selection for evidence.
- [ ] HTTP endpoint + JSON schema documented.
- [ ] `search_cvs` function ready to register as an agent tool.
- [ ] Sane server-side caps on limits.

---

## 2.11 Handoff to Phase 3

Phase 3 needs:

- **`search_cvs`** returning structured `cv_id` + chunks + scores.
- Optional **`get_cv_document(cv_id)`** stub or real implementation loading full text from DB if agents need more than top chunks ([§6.2](../CV_DISCOVERY_PIPELINE.md)).

Next: [Phase 3 — Agent workflow](./PHASE_3_AGENT_WORKFLOW.md).
