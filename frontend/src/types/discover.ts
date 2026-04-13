/** Mirrors `cv_agent.discovery.schemas` + `ChunkHit`. */

export interface ChunkHit {
  chunk_index: number;
  score: number;
  text: string;
  source?: string | null;
}

export interface SkillMatchResult {
  cv_id: string;
  skills_covered_pct: number;
  matched_skills: string[];
  missing_skills: string[];
  partial_matches: string[];
  comment: string;
}

export interface SkillMatchBreakdown {
  vector: number;
  skills_coverage: number;
}

export interface DiscoverResultRow {
  rank: number;
  cv_id: string;
  composite_score: number;
  skill_match: SkillMatchResult;
  breakdown: SkillMatchBreakdown;
  retrieval_chunks: ChunkHit[];
}

export interface JobSkillsSummary {
  required_skills: string[];
  must_have: string[];
  nice_to_have: string[];
}

export interface DiscoverModelIds {
  cv_skills?: string;
  jd_skills?: string;
  matcher?: string;
}

export interface DiscoverMeta {
  model_ids?: DiscoverModelIds;
  latency_ms?: Record<string, number>;
  warnings?: string[];
  retrieval_empty?: boolean;
}

export interface DiscoverResponse {
  job_skills: JobSkillsSummary;
  results: DiscoverResultRow[];
  meta?: DiscoverMeta;
}

export interface DiscoverRequest {
  query?: string;
  job_description?: string | null;
  top_k?: number;
}
