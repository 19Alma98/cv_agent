# Phase 4 — Quality and operations

**Parent document:** [CV discovery pipeline](../CV_DISCOVERY_PIPELINE.md) · §8 Phase 4, §1.2, §10  
**Prerequisites:** [Phase 3 — Agent workflow](./PHASE_3_AGENT_WORKFLOW.md) complete (end-to-end `/discover` in staging).

This phase makes the system **observable**, **cost-aware**, and **regression-testable** when you change models, prompts, or weights. It is not “more features”; it is what keeps a retrieval + multi-agent pipeline maintainable in production.

---

## 4.1 Purpose and outcomes

**Goal:**

1. **Logging and tracing** — Every `/discover` request is traceable across criteria → retrieval → rater calls → merge.
2. **Cost estimates** — Per request (or per stage): tokens, embedding calls, approximate USD (or internal credits).
3. **Optional human feedback loop** — Capture HR thumbs up/down or star ratings on results to tune merge weights or prompts ([§8](../CV_DISCOVERY_PIPELINE.md)).
4. **Evaluation set** — Labeled good/bad matches for **regression** after model or pipeline changes ([§8](../CV_DISCOVERY_PIPELINE.md)).

**Phase complete when:**

- Operators can answer: “Why was CV X ranked above Y for this query?” using logs/traces.
- You can compare **before/after** metrics on a frozen eval set when swapping embedding or chat models.
- Runbooks exist for common failures (Qdrant down, rate limits, empty index).

---

## 4.2 Logging (what to log)

**Correlation:**

- Generate a **`request_id`** (UUID) at API entry; pass it through every internal call and include it in all log lines.

**Per stage (structured fields):**

| Stage | Fields (examples) |
|--------|-------------------|
| API | `query` (consider hashing or truncating for PII), `top_k`, `user_id`/`tenant_id` if applicable |
| Criteria agent | model id, prompt version, output `job_spec` summary (not necessarily full JSON at INFO) |
| Embedding | model id, input length, latency ms |
| Qdrant | collection, k′, latency ms, hit count |
| Raters | per `cv_id`: model id, token usage, latency; **do not** log full CV text at default level |
| Merge | weights used, composite scores list |

**Levels:**

- **DEBUG:** chunk text snippets (only in secure dev environments).
- **INFO:** stage timings, counts, ids.
- **WARN:** retries, fallbacks, truncated CVs.
- **ERROR:** exceptions with stack traces (sanitize secrets).

**PII reminder ([§7](../CV_DISCOVERY_PIPELINE.md), [§10.5](../CV_DISCOVERY_PIPELINE.md)):** Define retention and redaction for logs that could contain CV excerpts or queries naming individuals.

---

## 4.3 Tracing

**Options:**

- **OpenTelemetry** traces spanning FastAPI → httpx (embedding/LLM) → qdrant-client spans.
- Or vendor-native tracing if you use a hosted LLM with built-in trace ids.

**Minimum viable:**

- One **parent span** per `/discover` and **child spans** for: `criteria`, `embed_query`, `qdrant_search`, `technical_rater`, `soft_rater`, `merge`.

**Attributes to attach:**

- `request_id`, `cv_count_scored`, `k_prime`, `top_k`, model names, status.

This satisfies debugging “slow request” and “which step failed?” without reading unstructured logs only.

---

## 4.4 Cost estimation per query

**Components:**

1. **Embeddings** — tokens in `retrieval_query` × price per 1K tokens (document formula in code comments or config).
2. **Criteria agent** — input + output tokens from provider usage metadata.
3. **Rater agents** — sum over all scored CVs: each call’s tokens (large if you send long context).

**Implementation sketch:**

- Wrap LLM clients to capture `usage.prompt_tokens` and `usage.completion_tokens` where available.
- Maintain a **small pricing table** in config (per model id) for estimates; mark values as **estimates** in API `meta` if exposed.

**Product use:**

- Return optional `meta.cost_estimate_usd` on `/discover` for internal tools only, or log it for finance dashboards.

**Guardrails ([§1.2](../CV_DISCOVERY_PIPELINE.md)):**

- Enforce **max CVs scored** and **max tokens per rater call** to cap worst-case cost.
- Alert if p95 cost exceeds threshold after a deploy.

---

## 4.5 Human feedback loop (optional)

**Goal:** Let HR signal quality so you can **adjust merge weights** or **prompt templates** without pure guesswork.

**Minimal design:**

- **POST /feedback** with `{ "request_id", "cv_id", "rating": "up" | "down", "comment": optional }`.
- Store in a **feedback table** (same DB as app or analytics store).

**Using feedback (v1):**

- Offline analysis: correlate downvotes with low `soft_avg` vs `technical_avg` → tweak default weights in `JobSpec` defaults.
- Later: train a small calibrator or bandit over weights (out of scope for initial loop).

**Privacy:** Align with HR and legal on storing queries and comments.

---

## 4.6 Evaluation set (regression)

**Goal:** After changing **embedding model**, **chat model**, **chunking**, or **prompts**, you can run an automated or semi-automated suite and compare metrics.

**Dataset format (example):**

| field | description |
|--------|----------------|
| `eval_id` | stable id |
| `query` | HR text |
| `relevant_cv_ids` | set of ids that should appear in top k |
| `irrelevant_cv_ids` | optional hard negatives |
| `notes` | human-readable |

**Metrics (simple start):**

- **Recall@k** — Any relevant `cv_id` in top k results.
- **MRR** — Mean reciprocal rank of first relevant CV.
- **Pairwise accuracy** — For labeled pairs (A better than B), does composite score agree?

**Runner:**

- Script: `uv run python -m cv_agent.eval.run --suite path/to/yaml --base-url https://staging...`
- Outputs: JSON report + exit code if below threshold (for CI).

**Frozen snapshots:**

- Pin **ingestion version** and **model ids** in eval config so a failing run is attributable to a specific change.

---

## 4.7 Dashboards and alerts

**Suggested panels:**

- Request rate, p50/p95 latency per stage, error rate by type.
- Qdrant latency and collection point count.
- Daily estimated cost from token usage aggregates.

**Alerts:**

- Qdrant health check fails ([§7](../CV_DISCOVERY_PIPELINE.md) `/health`).
- Spike in 503 or LLM errors.
- Eval suite regression after merge to main.

---

## 4.8 Runbooks (short)

Document in wiki or `docs/runbooks/`:

1. **Qdrant full** / disk — expand volume, prune old collections, or scale cluster.
2. **Embedding API rate limit** — reduce concurrency, increase backoff, raise quota.
3. **Bad rankings after deploy** — roll back, run eval suite, compare `job_spec` distributions in logs.
4. **Reindex required** — trigger Phase 1 `reindex --full` when embedding model changes ([§1.6](./PHASE_1_INGESTION_QDRANT.md)).

---

## 4.9 Checklist

- [ ] `request_id` propagated; structured logging per stage.
- [ ] Tracing (OTel or equivalent) for `/discover` critical path.
- [ ] Token usage captured; cost estimate logged or returned (internal).
- [ ] Caps on scored CVs and context size documented and enforced.
- [ ] Eval dataset + runner + at least one baseline metric recorded.
- [ ] Optional feedback API + storage (if product wants it).
- [ ] Runbooks for Qdrant, rate limits, reindex.

---

## 4.10 Relation to non-goals

Parent [§9](../CV_DISCOVERY_PIPELINE.md): automation does not replace human hiring decisions. Eval and feedback should support **assistive** quality, not automated acceptance thresholds unless policy explicitly allows.

---

## 4.11 References

- [CV discovery pipeline](../CV_DISCOVERY_PIPELINE.md) — goals, caveats, open decisions.
- Phase docs: [0](./PHASE_0_FOUNDATIONS.md) · [1](./PHASE_1_INGESTION_QDRANT.md) · [2](./PHASE_2_RETRIEVAL_ONLY.md) · [3](./PHASE_3_AGENT_WORKFLOW.md)
