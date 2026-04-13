from __future__ import annotations

from pydantic import BaseModel, Field

from cv_agent.retrieval.models import ChunkHit


class SkillItem(BaseModel):
    """One technical skill extracted from a CV."""

    name: str = Field(..., description="Canonical skill name, e.g. Python, Kubernetes")
    aliases: list[str] = Field(default_factory=list, description="Surface forms from the CV")
    evidence: str | None = Field(
        default=None,
        description="Short quote or paraphrase for non-obvious skills",
    )


class CandidateSkills(BaseModel):
    cv_id: str
    skills: list[SkillItem] = Field(default_factory=list)
    notes: str | None = Field(default=None, description="Ambiguities or caveats")


class JobRequiredSkills(BaseModel):
    """Skills required by the job description (Agent B output)."""

    job_id: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    seniority_hints: str | None = None
    inference: bool = Field(
        default=False,
        description="True if stack was inferred from a vague JD",
    )
    confidence: str | None = Field(
        default=None,
        description="Optional coarse confidence when inference is true",
    )


class SkillMatchResult(BaseModel):
    cv_id: str
    skills_covered_pct: float = Field(..., ge=0.0, le=100.0)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    partial_matches: list[str] = Field(default_factory=list)
    comment: str = Field(..., description="HR-readable summary, consistent with lists")


class JobSkillsSummary(BaseModel):
    """Subset of job skills exposed on the discover response."""

    required_skills: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)


class SkillMatchBreakdown(BaseModel):
    vector: float = Field(..., description="Normalized retrieval score in [0,1] for this batch")
    skills_coverage: float = Field(..., description="skills_covered_pct / 100")


class DiscoverResultRow(BaseModel):
    rank: int
    cv_id: str
    composite_score: float
    skill_match: SkillMatchResult
    breakdown: SkillMatchBreakdown
    retrieval_chunks: list[ChunkHit] = Field(default_factory=list)


class DiscoverModelIds(BaseModel):
    cv_skills: str = ""
    jd_skills: str = ""
    matcher: str = ""


class DiscoverMeta(BaseModel):
    model_ids: DiscoverModelIds = Field(default_factory=DiscoverModelIds)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    retrieval_empty: bool = False


class DiscoverRequest(BaseModel):
    query: str = ""
    job_description: str | None = None
    top_k: int = Field(default=20, ge=1, le=100)


class DiscoverResponse(BaseModel):
    job_skills: JobSkillsSummary
    results: list[DiscoverResultRow]
    meta: DiscoverMeta = Field(default_factory=DiscoverMeta)
