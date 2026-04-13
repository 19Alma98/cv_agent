from __future__ import annotations

import asyncio
import importlib.metadata
import logging
import time
from typing import Any

import agent_framework as _agent_framework_pkg

if not hasattr(_agent_framework_pkg, "__version__"):
    try:
        _af_ver = importlib.metadata.version("agent-framework")
    except importlib.metadata.PackageNotFoundError:
        _af_ver = "1.0.0"
    setattr(_agent_framework_pkg, "__version__", _af_ver)

from agent_framework._agents import Agent
from agent_framework._types import AgentResponse, ChatOptions, Message
from agent_framework_openai import OpenAIChatCompletionClient
from qdrant_client import QdrantClient

from cv_agent.config import Settings
from cv_agent.discovery.llm_client import build_async_openai_chat_client
from cv_agent.discovery.merge import (
    VectorMergeInput,
    denominator_skills,
    merge_batch,
    reconcile_match_percent,
    sort_merge_outputs,
)
from cv_agent.discovery.prompts import (
    AGENT_A_INSTRUCTIONS,
    AGENT_B_INSTRUCTIONS,
    AGENT_C_INSTRUCTIONS,
)
from cv_agent.discovery.schemas import (
    CandidateSkills,
    DiscoverMeta,
    DiscoverModelIds,
    DiscoverRequest,
    DiscoverResponse,
    DiscoverResultRow,
    JobRequiredSkills,
    JobSkillsSummary,
    SkillMatchBreakdown,
    SkillMatchResult,
)
from cv_agent.discovery.tools import build_retrieval_function_tools
from cv_agent.retrieval.cv_document import fetch_cv_document_text
from cv_agent.retrieval.models import CvHit, RetrievalResult
from cv_agent.retrieval.search import RetrievalServiceError, search_cvs

logger = logging.getLogger(__name__)


class DiscoverError(Exception):
    """User-facing discover failures."""


def _validate_llm_config(settings: Settings) -> None:
    if not settings.llm_model.strip():
        raise DiscoverError("LLM_MODEL is required for POST /discover")
    if settings.llm_provider != "azure_foundry" and not settings.llm_api_key.strip():
        raise DiscoverError("LLM_API_KEY is required for this LLM_PROVIDER")


def _chat_options(
    response_format: type,
    settings: Settings,
    *,
    temperature: float = 0.2,
) -> ChatOptions:
    opts: dict[str, Any] = {
        "response_format": response_format,
        "temperature": temperature,
        "model": settings.llm_model,
    }
    return opts  # type: ignore[return-value]


def _jd_text(body: DiscoverRequest) -> str:
    jd = (body.job_description or "").strip()
    if jd:
        return jd
    return body.query.strip()


def _retrieval_query(body: DiscoverRequest) -> str:
    q = body.query.strip()
    if q:
        return q
    return (body.job_description or "").strip()


def _fallback_candidate(cv_id: str, note: str) -> CandidateSkills:
    return CandidateSkills(cv_id=cv_id, skills=[], notes=note)


def _fallback_match(cv_id: str, job: JobRequiredSkills, comment: str) -> SkillMatchResult:
    req = denominator_skills(job)
    return SkillMatchResult(
        cv_id=cv_id,
        skills_covered_pct=0.0,
        matched_skills=[],
        missing_skills=list(req),
        partial_matches=[],
        comment=comment,
    )


async def _run_agent(
    agent: Agent,
    user_text: str,
    options: ChatOptions,
    timeout: float,
) -> Any:
    async def _call() -> Any:
        resp = agent.run(
            messages=[Message("user", [user_text])],
            options=options,
        )
        return await resp

    result = await asyncio.wait_for(_call(), timeout=timeout)
    if isinstance(result, AgentResponse):
        return result.value
    return result


async def run_discover(
    body: DiscoverRequest,
    settings: Settings,
    qdrant: QdrantClient,
) -> DiscoverResponse:
    """
    Phase 3 workflow: retrieval → Agent B → (Agent A + Agent C per CV) → deterministic merge.

    Registers retrieval tools on the three agents for Microsoft Agent Framework tool wiring;
    runs are single-turn structured outputs (orchestration loads CV text directly).
    """
    _validate_llm_config(settings)
    t0 = time.perf_counter()
    latency: dict[str, float] = {}
    warnings: list[str] = []

    retrieval_tools = build_retrieval_function_tools()

    async_client = build_async_openai_chat_client(settings)
    chat_client = OpenAIChatCompletionClient(
        async_client=async_client,
        model=settings.llm_model.strip() or None,
    )

    agent_b = Agent(
        client=chat_client,
        name="jd_skills",
        instructions=AGENT_B_INSTRUCTIONS,
        tools=retrieval_tools,
    )
    agent_a = Agent(
        client=chat_client,
        name="cv_skills",
        instructions=AGENT_A_INSTRUCTIONS,
        tools=retrieval_tools,
    )
    agent_c = Agent(
        client=chat_client,
        name="skill_match",
        instructions=AGENT_C_INSTRUCTIONS,
        tools=retrieval_tools,
    )

    rq = _retrieval_query(body)
    top_cvs = min(settings.discover_retrieval_limit_cvs, settings.search_max_limit_cvs)
    top_chunks = min(settings.discover_retrieval_limit_chunks, settings.search_max_limit_chunks)

    try:
        retrieval: RetrievalResult = search_cvs(
            rq,
            settings,
            qdrant,
            top_k_cvs=top_cvs,
            top_k_chunks=top_chunks,
        )
    except RetrievalServiceError as e:
        raise DiscoverError(str(e)) from e
    except ValueError as e:
        raise DiscoverError(str(e)) from e

    latency["retrieval_ms"] = (time.perf_counter() - t0) * 1000

    if not retrieval.cvs:
        return DiscoverResponse(
            job_skills=JobSkillsSummary(),
            results=[],
            meta=DiscoverMeta(
                model_ids=DiscoverModelIds(
                    cv_skills=settings.llm_model,
                    jd_skills=settings.llm_model,
                    matcher=settings.llm_model,
                ),
                latency_ms=latency,
                warnings=warnings,
                retrieval_empty=True,
            ),
        )

    jd = _jd_text(body)
    t_b = time.perf_counter()
    try:
        job = await _run_agent(
            agent_b,
            jd,
            _chat_options(JobRequiredSkills, settings),
            settings.discover_llm_timeout_s,
        )
    except TimeoutError:
        raise DiscoverError("LLM timeout while extracting job skills") from None
    if not isinstance(job, JobRequiredSkills):
        raise DiscoverError("Job skills agent returned invalid structured output: " + str(job))
    latency["job_skills_ms"] = (time.perf_counter() - t_b) * 1000

    cvs = retrieval.cvs
    n = min(len(cvs), settings.discover_max_cvs_to_score)
    cvs_to_score = cvs[:n]
    if len(cvs) > n:
        warnings.append(f"scored_{n}_of_{len(cvs)}_retrieved_cvs")

    sem = asyncio.Semaphore(settings.discover_llm_concurrency)

    async def score_one(hit: CvHit) -> tuple[str, SkillMatchResult, str | None]:
        note: str | None = None
        async with sem:
            t_cv = time.perf_counter()
            try:
                doc = await asyncio.to_thread(
                    fetch_cv_document_text,
                    qdrant,
                    settings,
                    hit.cv_id,
                    max_chars=settings.discover_max_cv_text_chars,
                )
            except Exception as e:
                logger.warning("get_cv_document failed cv_id=%s err=%s", hit.cv_id, e)
                doc_txt = ""
                trunc = False
                note = "document_load_failed"
            else:
                doc_txt = doc.text
                trunc = doc.truncated
                if doc.truncated:
                    note = "cv_text_truncated"

            user_a = (
                f"cv_id: {hit.cv_id}\n"
                f"truncated: {trunc}\n\n"
                f"CV text:\n{doc_txt}"
            )
            try:
                cand_val = await _run_agent(
                    agent_a,
                    user_a,
                    _chat_options(CandidateSkills, settings),
                    settings.discover_llm_timeout_s,
                )
            except TimeoutError:
                warnings.append(f"cv_skills_timeout:{hit.cv_id}")
                cand = _fallback_candidate(hit.cv_id, "LLM timeout (CV skills).")
            else:
                if isinstance(cand_val, CandidateSkills):
                    cand = cand_val.model_copy(update={"cv_id": hit.cv_id})
                else:
                    warnings.append(f"cv_skills_parse_failed:{hit.cv_id}")
                    cand = _fallback_candidate(
                        hit.cv_id,
                        "Invalid structured output from CV skills agent.",
                    )

            user_c = (
                "Job skills (JSON):\n"
                f"{job.model_dump_json()}\n\n"
                "Candidate skills (JSON):\n"
                f"{cand.model_dump_json()}"
            )
            try:
                match_val = await _run_agent(
                    agent_c,
                    user_c,
                    _chat_options(SkillMatchResult, settings),
                    settings.discover_llm_timeout_s,
                )
            except TimeoutError:
                warnings.append(f"match_timeout:{hit.cv_id}")
                match = _fallback_match(hit.cv_id, job, "LLM timeout (skill match).")
            else:
                if isinstance(match_val, SkillMatchResult):
                    match = match_val.model_copy(update={"cv_id": hit.cv_id})
                else:
                    warnings.append(f"match_parse_failed:{hit.cv_id}")
                    match = _fallback_match(
                        hit.cv_id,
                        job,
                        "Invalid structured output from match agent.",
                    )

            match = reconcile_match_percent(job, match)
            latency[f"cv_{hit.cv_id}_ms"] = (time.perf_counter() - t_cv) * 1000
            return hit.cv_id, match, note

    t_batch = time.perf_counter()
    scored = await asyncio.gather(*[score_one(h) for h in cvs_to_score])
    latency["per_cv_total_ms"] = (time.perf_counter() - t_batch) * 1000

    by_cv: dict[str, SkillMatchResult] = {}
    notes_by_cv: dict[str, str | None] = {}
    for cv_id, match, n in scored:
        by_cv[cv_id] = match
        notes_by_cv[cv_id] = n

    vector_scores = {h.cv_id: h.score for h in cvs_to_score}
    merge_inputs = [
        VectorMergeInput(
            cv_id=h.cv_id,
            vector_score=h.score,
            skills_covered_pct=by_cv[h.cv_id].skills_covered_pct,
        )
        for h in cvs_to_score
    ]
    merged = merge_batch(
        merge_inputs,
        w_cov=settings.discover_w_coverage,
        w_v=settings.discover_w_vector,
    )
    skills_pct = {m.cv_id: by_cv[m.cv_id].skills_covered_pct for m in merged}
    ordered = sort_merge_outputs(merged, vector_scores, skills_pct)

    hit_by_id = {h.cv_id: h for h in cvs_to_score}
    rows: list[DiscoverResultRow] = []
    for rank, m in enumerate(ordered[: body.top_k], start=1):
        hit = hit_by_id[m.cv_id]
        sm = by_cv[m.cv_id]
        note = notes_by_cv.get(m.cv_id)
        if note and note not in sm.comment:
            sm = sm.model_copy(update={"comment": f"{sm.comment} ({note})"})

        rows.append(
            DiscoverResultRow(
                rank=rank,
                cv_id=m.cv_id,
                composite_score=m.composite_score,
                skill_match=sm,
                breakdown=SkillMatchBreakdown(
                    vector=m.v_norm,
                    skills_coverage=sm.skills_covered_pct / 100.0,
                ),
                retrieval_chunks=list(hit.chunks),
            )
        )

    return DiscoverResponse(
        job_skills=JobSkillsSummary(
            required_skills=list(job.required_skills),
            must_have=list(job.must_have),
            nice_to_have=list(job.nice_to_have),
        ),
        results=rows,
        meta=DiscoverMeta(
            model_ids=DiscoverModelIds(
                cv_skills=settings.llm_model,
                jd_skills=settings.llm_model,
                matcher=settings.llm_model,
            ),
            latency_ms=latency,
            warnings=warnings,
            retrieval_empty=False,
        ),
    )
