# Phase 3 — Agent workflow

**Parent document:** [CV discovery pipeline](../CV_DISCOVERY_PIPELINE.md) · §3, §6, §7, §8 Phase 3  
**Prerequisites:** [Phase 2 — Retrieval only](./PHASE_2_RETRIEVAL_ONLY.md) complete.

This phase wires the **Microsoft Agent Framework** workflow: **criteria agent** → **retrieval** (tool) → **parallel technical + soft-skill raters** → **deterministic merge** → **POST /discover** response with ranked CVs, scores, and evidence.

---

## 3.1 Purpose and outcomes

**Goal:** HR sends a natural language query; the system returns a **shortlist** with:

- **Final ranking** and **composite score** (or explicit dimension breakdown).
- **Per-dimension scores** and **evidence snippets** tied to retrieved chunks ([§6.3](../CV_DISCOVERY_PIPELINE.md)).
- **Criteria echo**: what the system understood as must-have / nice-to-have (auditable).

**Phase complete when:**

1. End-to-end **`POST /discover`** matches the intent of parent [§7](../CV_DISCOVERY_PIPELINE.md).
2. Workflow is expressed as an **Agent Framework workflow** (not a one-off script), with **tools** for Qdrant search and optional full CV load ([§6.2](../CV_DISCOVERY_PIPELINE.md)).
3. Agent outputs conform to **Pydantic (JSON) schemas** suitable for UI and logging.
4. **Merge** combines vector rank signals + agent scores using **weights from the criteria agent** ([§6.4](../CV_DISCOVERY_PIPELINE.md)).

---

## 3.2 Workflow graph (execution order)

Recommended **sequential + fan-out** pattern ([§6.4](../CV_DISCOVERY_PIPELINE.md)):

```text
1. Criteria agent
   Input: HR query (+ optional org defaults)
   Output: JobSpec (structured) + retrieval_query_text + optional metadata filters

2. Embed retrieval_query_text (or multiple strings if you extend JobSpec)
   Call existing embed_query from Phase 2

3. search_cvs(retrieval_query_text, filters from JobSpec, limits)
   Output: list of { cv_id, chunk evidence, vector-derived rank/score }

4. Working set truncation
   If needed, pass only top N CVs (e.g. 10–20) to expensive LLM steps

5. Parallel (conceptually) — Technical rater + Soft-skills rater
   Each input: JobSpec + same chunk bundle per cv_id (+ optional full CV from get_cv_document)
   Each output: Scores [0,1] per named criterion + evidence strings

6. Merge (deterministic Python)
   Weighted combination + tie-break rules → final ordering

7. Optional: short narrative block (template from scores or small synthesizer agent — parent §6.1 optional fourth agent)
```

Use the framework’s primitives for **sequential steps**, **parallel branches**, and **tool invocation**; avoid ad-hoc global state — pass explicit context objects between steps.

---

## 3.3 Agent 1 — Criteria / planner

**Role:** Normalize messy HR language into a **checkable** specification and a **retrieval-optimized** query string ([§3](../CV_DISCOVERY_PIPELINE.md), table in [§6.1](../CV_DISCOVERY_PIPELINE.md)).

**Suggested `JobSpec` fields (Pydantic):**

| Field | Purpose |
|--------|---------|
| `must_have` | List of requirements (skill, level hint, years if any) |
| `nice_to_have` | Same structure, lower priority |
| `seniority` | e.g. junior / mid / senior / lead — free text or enum |
| `domain` | e.g. fintech, healthcare |
| `constraints` | location, language, employment type |
| `retrieval_query` | One string optimized for embedding (synonyms, stack names) |
| `retrieval_queries` | Optional list if you implement multi-vector search later |
| `weights` | Numeric weights for merge: e.g. `technical`, `soft`, `vector` |
| `qdrant_filter` | Optional structured filter compatible with your payload schema |

**Prompting guidelines:**

- Ask the model to **avoid** inventing hard numbers not implied by the user unless marked as inference.
- Require **valid JSON** matching the schema; use structured output mode if your provider supports it.
- Include **short rationale** field optional for debugging (not shown to HR if too noisy).

---

## 3.4 Tool: `search_cvs`

Wire Phase 2’s function as a **framework tool** with a schema derived from its signature:

- Parameters: `query`, `top_k_cvs`, `top_k_chunks`, optional `filters`.
- Returns: serialized `RetrievalResult` the agents do not mutate.

The **criteria agent** does not call Qdrant directly; the **workflow orchestration** calls `embed` + `search_cvs` using the criteria output (cleaner tracing).

---

## 3.5 Tool: `get_cv_document` (optional but valuable)

**Role:** Load **full CV text** or all chunks from your DB when top-k chunks are insufficient ([§6.2](../CV_DISCOVERY_PIPELINE.md)).

**Behavior:**

- Input: `cv_id`
- Output: plain text or list of sections
- Enforce **max length** before sending to LLM (truncate with ellipsis + note in evidence)

If not implemented, raters use **only** retrieved chunks (acceptable for v1 if chunks are rich).

---

## 3.6 Agent 2 — Technical rater

**Input:** `JobSpec` + for one `cv_id` the bundle of chunk texts (and scores).

**Output schema (example):**

```json
{
  "cv_id": "...",
  "criteria_scores": {
    "java_proficiency": 0.85,
    "spring_ecosystem": 0.7,
    "microservices": 0.6
  },
  "evidence": {
    "java_proficiency": "Quote or paraphrase from chunk 2...",
    "spring_ecosystem": "..."
  },
  "gaps": ["No explicit Kubernetes mentioned"]
}
```

**Rules ([§6.3](../CV_DISCOVERY_PIPELINE.md)):**

- Scores in **[0, 1]** with **named dimensions** aligned to `JobSpec` (dynamic list or fixed template — if dynamic, merge step must map names safely).
- **Evidence:** 1–3 short strings per non-trivial criterion; must cite or closely paraphrase provided chunks (reduces hallucination).

**Batching:** For many CVs, either **one LLM call per CV** (simple, more cost) or **batched multi-CV prompt** (complex, cheaper). Start with **per-CV** for clarity.

---

## 3.7 Agent 3 — Soft-skills rater

Same contract as technical rater with different criterion names, e.g. `communication`, `leadership`, `collaboration`, `ownership`.

**Orthogonality:** Keep prompts from double-counting the same bullet as both “technical depth” and “leadership” unless justified.

---

## 3.8 Merge step (deterministic)

**Inputs:**

- Vector-derived rank or normalized score per `cv_id` from Phase 2 collapse.
- Technical `criteria_scores` and soft `criteria_scores`.
- `JobSpec.weights` (and default weights if missing).

**Suggested v1 formula (example):**

1. Normalize vector score per batch (e.g. min-max across the working set) → `v_norm`.
2. `technical_avg` = mean of technical scores (or weighted by criterion importance from JobSpec if provided).
3. `soft_avg` = mean of soft scores.
4. `composite = w_v * v_norm + w_t * technical_avg + w_s * soft_avg` with weights summing to 1.

**Tie-break:** Higher `technical_avg`, then higher vector raw score, then stable `cv_id` sort.

**Output:** Sorted list of records for API response: `cv_id`, `composite`, breakdown, evidence objects, optional `gaps`.

**Calibration note ([§1.2](../CV_DISCOVERY_PIPELINE.md)):** Treat LLM scores as **relative within the batch**; document this in API field descriptions for consumers.

---

## 3.9 POST /discover contract

**Request ([§7](../CV_DISCOVERY_PIPELINE.md)):**

```json
{
  "query": "We need a Java tech lead with mentoring experience",
  "top_k": 20
}
```

**Response (illustrative — adjust to your UI):**

```json
{
  "job_spec": { ... },
  "results": [
    {
      "rank": 1,
      "cv_id": "...",
      "composite_score": 0.91,
      "breakdown": {
        "vector": 0.88,
        "technical": 0.92,
        "soft": 0.85
      },
      "evidence": { ... },
      "retrieval_chunks": [ ... ]
    }
  ],
  "meta": {
    "model_ids": { "criteria": "...", "technical": "...", "soft": "..." },
    "latency_ms": { ... },
    "ingestion_hint": "embedding_model_id used for search"
  }
}
```

**Parameters:**

- `top_k` maps to **final** shortlist size; internally you may use larger retrieval k′ and smaller scoring set ([§1.2](../CV_DISCOVERY_PIPELINE.md)).

---

## 3.10 Error handling and guardrails

- **Criteria parse failure:** Return `400` with validation errors; do not call retrieval.
- **Empty retrieval:** Return empty `results` with explanation in `meta`.
- **LLM timeout / rate limit:** Partial results policy — either fail whole request with `503` or return retrieval-only ranking with `meta.warning` (choose one and document).
- **PII:** Avoid logging full CV text at INFO; use redaction or ids only ([§7](../CV_DISCOVERY_PIPELINE.md)).

---

## 3.11 Testing

- **Golden-path test** with mocked LLM responses (fixed JSON) to test merge and API shape.
- **Integration test** (gated): small real query against staging Qdrant + test CVs.
- **Contract tests:** Pydantic models round-trip JSON used by the frontend.

---

## 3.12 Pitfalls

- **Scoring 50 CVs × 2 agents** — cost explosion; enforce **working set** size ([§1.2](../CV_DISCOVERY_PIPELINE.md)).
- **Schema drift** between agents and merge — use shared enums / field lists from `JobSpec`.
- **Bypassing Agent Framework** “just once” — tends to stick; keep workflow in the framework for maintainability ([workspace rules](../../.cursor/rules/agent-framework.mdc)).

---

## 3.13 Checklist

- [ ] Criteria agent + `JobSpec` schema + structured output.
- [ ] Workflow wires embed + `search_cvs` + truncation.
- [ ] Technical + soft agents with evidence fields.
- [ ] Merge implements weights + tie-breaks.
- [ ] `POST /discover` documented and implemented.
- [ ] Tools registered per Agent Framework patterns.
- [ ] Basic tests with mocked LLM and one integration path.

---

## 3.14 Handoff to Phase 4

Phase 4 adds **observability**, **cost/latency accounting**, **evaluation sets**, and optional **human feedback** on weights ([§8 Phase 4](../CV_DISCOVERY_PIPELINE.md)).

Next: [Phase 4 — Quality and operations](./PHASE_4_QUALITY_AND_OPERATIONS.md).
