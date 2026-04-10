# Phase 3 — Agent workflow

**Parent document:** [CV discovery pipeline](../CV_DISCOVERY_PIPELINE.md) · §3, §6, §7, §8 Phase 3  
**Prerequisites:** [Phase 2 — Retrieval only](./PHASE_2_RETRIEVAL_ONLY.md) complete.

This phase wires the **Microsoft Agent Framework** workflow around **technical skills**: estrazione dalle fonti testuali, **match** candidato ↔ posizione, poi (per la shortlist) **combinazione** con il segnale vettoriale da Phase 2 e risposta **`POST /discover`**.

---

## 3.1 Purpose and outcomes

**Goal:** Per ogni candidato nella working set, il sistema produce:

- **Lista normalizzata** di skill tecniche emerse dal **CV** (solo ciò che è tecnico, niente narrativa generica se non serve al match).
- **Lista** di skill tecniche **richieste** dalla **job description** (cosa serve per essere un buon candidato).
- **Match**: **percentuale di copertura** (`skills covered` rispetto al set richiesto), elenco **match / gap** opzionale, e un **commento** sintetico leggibile da HR.

**Phase complete when:**

1. End-to-end **`POST /discover`** (o endpoint dedicato “skill fit”) rispetta il contratto JSON concordato.
2. Il flusso è espresso come **workflow Agent Framework** (sequenza + eventuale parallelismo su più CV), con **tool** per Qdrant e caricamento testo CV ([§6.2](../CV_DISCOVERY_PIPELINE.md)).
3. Gli output degli agenti sono **Pydantic / JSON schema** stabili per UI e log.
4. Il **merge** per il ranking finale combina **coverage skills** (e opzionalmente altri segnali) con **score vettoriale** e regole di tie-break documentate.

---

## 3.2 Workflow graph (execution order)

Flusso consigliato: **una volta** estrazione requisiti da JD, **per ogni CV** estrazione skills + match; retrieval opzionale a monte per scegliere i CV da valutare.

```text
0. (Opzionale) Input HR
   - Se l’input è solo una query breve, uno step leggero può produrre o arricchire il testo “job description” usato dall’agente 2.
   - Se la JD è già fornita intera, saltare o ridurre questo step.

1. Phase 2 — Retrieval (tool + embed)
   search_cvs(...) → working set di cv_id + chunk (o testo via get_cv_document)

2. Agente A — Estrazione skill dal CV
   Input: testo CV (chunk top-k e/o full document, con limite lunghezza)
   Output: CandidateSkills (solo skill tecniche, con sinonimi normalizzati se definiti nello schema)

3. Agente B — Estrazione skill dalla job description
   Input: testo job description (o testo derivato dalla query HR)
   Output: JobRequiredSkills (skill tecniche necessarie per un buon fit; opzionale must_have / nice_to_have)

4. Agente C — Match skills + commento
   Input: CandidateSkills + JobRequiredSkills
   Output: SkillMatchResult (percentuale copertura, matched/missing opzionali, commento breve)

5. Merge (deterministico, Python)
   Per ogni cv_id: ranking da combinare es. w_cov * coverage_pct + w_v * v_norm (normalizzato sul batch)
   Tie-break: coverage, poi score vettoriale grezzo, poi cv_id stabile

6. (Opzionale) Sintesi batch per HR: template dai punteggi o piccolo agente narrativo
```

Usa i primitivi del framework per **step sequenziali** e **fan-out** sui CV; passa **oggetti di contesto espliciti** tra gli step (niente stato globale ad hoc).

---

## 3.3 Agente A — Estrazione skill tecniche dal CV

**Ruolo:** Dal **solo testo del CV**, estrarre **informazioni sulle skill tecniche** del candidato (linguaggi, framework, tool, cloud, DB, metodologie strettamente tecniche). Escludere o deprioritizzare contenuti non utili al match tecnico (hobby generici, testo boilerplate) salvo policy prodotto diversa.

**Input:** `cv_id` (per tracciamento), `cv_text` (o lista sezioni).

**Output schema (esempio Pydantic):**

| Campo | Scopo |
|--------|--------|
| `cv_id` | Allineamento al batch |
| `skills` | Lista di skill con `name` canonico + `aliases` opzionali dal testo |
| `evidence` | Opzionale: 1 stringa breve per skill “non ovvia” (citazione/parafrasi) |
| `notes` | Opzionale: ambiguità (“menziona Java ma non anni”) |

**Linee guida prompt:**

- Output **JSON valido** conforme allo schema; structured output se supportato.
- Non inventare skill non supportate dal testo fornito.
- Normalizzare sinonimi (es. “K8s” → `Kubernetes`) se lo schema prevede un vocabolario controllato o istruzioni di normalizzazione.

---

## 3.4 Agente B — Estrazione skill tecniche dalla job description

**Ruolo:** Dal **testo della job description** (o dal testo che rappresenta il ruolo), estrarre le **skill tecniche necessarie** per essere un **buon candidato** (stack atteso, tool, domini tecnici). Opzionale: separare **must_have** vs **nice_to_have** se utile al calcolo della percentuale.

**Input:** `job_description_text` (stringa); opzionale `job_id` per log.

**Output schema (esempio):**

| Campo | Scopo |
|--------|--------|
| `required_skills` | Lista skill attese (stessa granularità/convenzioni dell’agente A per favorire il match) |
| `must_have` / `nice_to_have` | Opzionale: sottoinsiemi per pesare la coverage |
| `seniority_hints` | Opzionale: solo se serve downstream (non obbligatorio per il match puro skills) |

**Linee guida prompt:**

- Discriminare skill **esplicitamente richieste** da competenze generiche (“ottima conoscenza Office”) se il prodotto le esclude dal set “tecnico”.
- Se la JD è vaga, il modello può inferire stack probabile ma conviene campo `inference: true` o `confidence` per audit.

---

## 3.5 Agente C — Match candidato ↔ JD e commento

**Ruolo:** Confrontare **CandidateSkills** (output A) e **JobRequiredSkills** (output B); calcolare **percentuale di skill coperte** e produrre un **commento** sintetico per HR.

**Input:** Output strutturati di A e B (non serve re-inviare tutto il CV/JD se i JSON sono sufficienti).

**Definizione consigliata di `skills_covered_pct`:**

- Denominatore: numero di skill in `JobRequiredSkills` (o solo `must_have` se usate due liste).
- Numeratore: skill richieste per cui esiste un match accettato (equivalenza/sinonimo decisa dal modello secondo regole fisse nello prompt o da lookup).
- Valore **0–100** intero o float a 1 decimale; documentare se `nice_to_have` entra nel denominatore.

**Output schema (esempio):**

```json
{
  "cv_id": "...",
  "skills_covered_pct": 72.5,
  "matched_skills": ["Python", "PostgreSQL"],
  "missing_skills": ["Kubernetes"],
  "partial_matches": [],
  "comment": "Forte allineamento su backend e dati; manca esperienza esplicita su orchestrazione container."
}
```

**Regole:**

- Il **commento** deve essere coerente con **matched** / **missing**; evitare contraddizioni con le liste.
- Opzionale: seconda passata **deterministica** che ricalcola la % dalle liste per evitare errori aritmetici del modello (consigliato in produzione).

---

## 3.6 Tool: `search_cvs`

Come in Phase 2, esposto come **tool** del framework:

- Parametri: `query`, `top_k_cvs`, `top_k_chunks`, filtri opzionali.
- Restituisce `RetrievalResult` immutabile per gli agenti.

L’orchestrazione (non l’agente B) invoca **embed + search_cvs** usando la query HR o una `retrieval_query` derivata, per costruire la working set.

---

## 3.7 Tool: `get_cv_document` (consigliato per l’agente A)

**Ruolo:** Caricare **testo CV completo** o tutte le sezioni quando i chunk non bastano ([§6.2](../CV_DISCOVERY_PIPELINE.md)).

- Input: `cv_id`
- Output: testo o sezioni
- **Limite massimo** di caratteri prima dell’LLM (troncare con nota in metadata)

---

## 3.8 Merge step (deterministico)

**Input per CV:** `skills_covered_pct` (o score 0–1 derivato), score vettoriale normalizzato sul batch, pesi opzionali da config o da uno step “planner” leggero.

**Formula esempio:**

1. `cov_norm = skills_covered_pct / 100`
2. `v_norm` = normalizzazione min-max degli score retrieval nella working set
3. `composite = w_cov * cov_norm + w_v * v_norm` con pesi che sommano a 1

**Tie-break:** `skills_covered_pct` decrescente, poi score vettoriale grezzo, poi `cv_id`.

**Output API:** per ogni risultato: `rank`, `cv_id`, `composite_score`, `skill_match` (oggetto con %, liste, commento), `retrieval_chunks` opzionali.

---

## 3.9 POST /discover contract

**Request (illustrativo):**

```json
{
  "query": "Senior backend Python, PostgreSQL, Docker",
  "job_description": "Optional full JD text if different from query...",
  "top_k": 20
}
```

Se `job_description` è assente, il testo usato dall’**agente B** può essere la `query` o un’estensione generata nello step opzionale §3.2.

**Response (illustrativo):**

```json
{
  "job_skills": { "required_skills": ["Python", "PostgreSQL", "Kubernetes"] },
  "results": [
    {
      "rank": 1,
      "cv_id": "...",
      "composite_score": 0.88,
      "skill_match": {
        "skills_covered_pct": 66.7,
        "matched_skills": ["Python", "PostgreSQL"],
        "missing_skills": ["Kubernetes"],
        "comment": "..."
      },
      "breakdown": { "vector": 0.9, "skills_coverage": 0.667 },
      "retrieval_chunks": []
    }
  ],
  "meta": {
    "model_ids": { "cv_skills": "...", "jd_skills": "...", "matcher": "..." },
    "latency_ms": {}
  }
}
```

Parametro `top_k`: taglia finale della shortlist; internamente si può recuperare un k′ più grande e poi applicare agenti A/C solo sui primi N CV.

---

## 3.10 Error handling and guardrails

- **JD vuota / query non parsabile:** `400` con dettagli; non chiamare retrieval se manca input minimo.
- **Retrieval vuoto:** `results` vuoti e spiegazione in `meta`.
- **Timeout LLM:** policy unica (es. `503` o ranking solo vettoriale con `meta.warning`).
- **PII:** non loggare CV interi a INFO; usare id e redazione ([§7](../CV_DISCOVERY_PIPELINE.md)).
- **Allucinazioni sul match:** preferire **riconciliazione deterministica** della % dopo l’agente C.

---

## 3.11 Testing

- Test **golden path** con JSON fissi da A/B/C per verificare merge e forma della risposta.
- Test integrazione (opzionale): Qdrant staging + CV di prova.
- Contract test sui modelli Pydantic.

---

## 3.12 Pitfalls

- **Costo:** N CV × (agente A + agente C) + 1 × agente B; limitare N e riusare output B per tutto il batch.
- **Allineamento lessicale:** A e B devono usare **stesse convenzioni** di naming (prompt + glossario o post-processing).
- **Percentuale ambigua:** definire sempre cosa è nel denominatore (solo must-have o tutte le skill estratte).

---

## 3.13 Checklist

- [ ] Schemi Pydantic per `CandidateSkills`, `JobRequiredSkills`, `SkillMatchResult`.
- [ ] Agente A (CV skills), B (JD skills), C (match + commento) registrati nel workflow framework.
- [ ] Tool `search_cvs` + opzionale `get_cv_document` collegati.
- [ ] Merge con pesi + tie-break; risposta `POST /discover` allineata.
- [ ] Test con LLM mockati e un percorso integrazione.

---

## 3.14 Handoff to Phase 4

Phase 4 aggiunge **osservabilità**, **costi/latenza**, **evaluation set** e feedback umano ([§8 Phase 4](../CV_DISCOVERY_PIPELINE.md)).

Next: [Phase 4 — Quality and operations](./PHASE_4_QUALITY_AND_OPERATIONS.md).

---

## 3.15 Riferimento — modello precedente (criteria + rater tecnico/soft)

Il documento originale prevedeva **criteria/planner**, **technical rater**, **soft-skills rater** e merge su dimensioni 0–1. Se serve ancora scoring **soft skills** o criteri non riducibili a liste di skill, si può **aggiungere** un rater parallelo dopo il match skills oppure arricchire il commento dell’agente C con dimensioni soft — senza sostituire il flusso skills-first sopra, a meno di requisito prodotto esplicito.
