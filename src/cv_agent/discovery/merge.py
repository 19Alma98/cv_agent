from __future__ import annotations

from dataclasses import dataclass

from cv_agent.discovery.schemas import JobRequiredSkills, SkillMatchResult


def _norm(s: str) -> str:
    return " ".join(s.strip().casefold().split())


def denominator_skills(job: JobRequiredSkills) -> list[str]:
    """Denominator for coverage: must_have if non-empty, else required_skills."""
    if job.must_have:
        return list(job.must_have)
    return list(job.required_skills)


def recalculate_skills_covered_pct(
    job: JobRequiredSkills,
    matched_skills: list[str],
    missing_skills: list[str],
) -> float:
    """
    Deterministic coverage from lists (case-insensitive token match on full string).
    """
    required = denominator_skills(job)
    if not required:
        return 100.0
    matched_n = {_norm(x) for x in matched_skills if x.strip()}
    missing_n = {_norm(x) for x in missing_skills if x.strip()}
    covered = 0
    for r in required:
        rn = _norm(r)
        if not rn:
            continue
        if rn in matched_n and rn not in missing_n:
            covered += 1
    return round(100.0 * covered / len(required), 1)


def reconcile_match_percent(job: JobRequiredSkills, result: SkillMatchResult) -> SkillMatchResult:
    pct = recalculate_skills_covered_pct(job, result.matched_skills, result.missing_skills)
    return result.model_copy(update={"skills_covered_pct": pct})


@dataclass(frozen=True)
class VectorMergeInput:
    cv_id: str
    vector_score: float
    skills_covered_pct: float


@dataclass(frozen=True)
class VectorMergeOutput:
    cv_id: str
    composite_score: float
    v_norm: float
    cov_norm: float


def compute_v_norm_by_cv_id(vector_scores: dict[str, float]) -> dict[str, float]:
    """Min-max normalize vector scores to [0, 1] over the batch; single CV -> 1.0."""
    if not vector_scores:
        return {}
    scores = list(vector_scores.values())
    lo, hi = min(scores), max(scores)
    out: dict[str, float] = {}
    if hi <= lo:
        for k in vector_scores:
            out[k] = 1.0
        return out
    for k, s in vector_scores.items():
        out[k] = (s - lo) / (hi - lo)
    return out


def merge_batch(
    items: list[VectorMergeInput],
    *,
    w_cov: float,
    w_v: float,
) -> list[VectorMergeOutput]:
    """
    ``composite = w_cov * cov_norm + w_v * v_norm`` with ``cov_norm = pct/100``.
    Tie-break is applied by the caller (sort key).
    """
    w_sum = w_cov + w_v
    if w_sum <= 0:
        w_cov, w_v = 0.5, 0.5
        w_sum = 1.0
    w_cov /= w_sum
    w_v /= w_sum

    vmap = {x.cv_id: x.vector_score for x in items}
    v_norm = compute_v_norm_by_cv_id(vmap)

    merged: list[VectorMergeOutput] = []
    for x in items:
        cov = x.skills_covered_pct / 100.0
        vn = v_norm.get(x.cv_id, 0.0)
        comp = w_cov * cov + w_v * vn
        merged.append(
            VectorMergeOutput(
                cv_id=x.cv_id,
                composite_score=round(comp, 4),
                v_norm=round(vn, 4),
                cov_norm=round(cov, 4),
            )
        )
    return merged


def sort_merge_outputs(
    merged: list[VectorMergeOutput],
    vector_scores: dict[str, float],
    skills_pct: dict[str, float],
) -> list[VectorMergeOutput]:
    """Tie-break: skills_covered_pct desc, raw vector desc, cv_id asc."""

    def key(m: VectorMergeOutput) -> tuple:
        pct = skills_pct.get(m.cv_id, 0.0)
        raw = vector_scores.get(m.cv_id, 0.0)
        return (-m.composite_score, -pct, -raw, m.cv_id)

    return sorted(merged, key=key)
