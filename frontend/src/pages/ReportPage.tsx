import { Link } from "react-router-dom";
import { useMemo } from "react";
import { loadDiscoverReport } from "../storage";
import type { DiscoverResultRow } from "../types/discover";

function TagList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) {
    return null;
  }
  return (
    <div className="tag-block">
      <h3>{title}</h3>
      <ul className="tags">
        {items.map((t, i) => (
          <li key={`${t}-${i}`}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

function ResultCard({ row }: { row: DiscoverResultRow }) {
  const sm = row.skill_match;
  return (
    <article className="result-card">
      <div className="result-head">
        <span className="rank">#{row.rank}</span>
        <span className="cv-id">{row.cv_id}</span>
        <span className="score" title="Punteggio composito">
          {(row.composite_score * 100).toFixed(1)}%
        </span>
      </div>
      <p className="comment">{sm.comment}</p>
      <dl className="metrics">
        <div>
          <dt>Copertura skill</dt>
          <dd>{sm.skills_covered_pct.toFixed(0)}%</dd>
        </div>
        <div>
          <dt>Similarity score</dt>
          <dd>{row.breakdown.vector.toFixed(3)}</dd>
        </div>
      </dl>
      <TagList title="Match" items={sm.matched_skills} />
      <TagList title="Mancanti" items={sm.missing_skills} />
      <TagList title="Parziali" items={sm.partial_matches} />
      {row.retrieval_chunks.length > 0 ? (
        <details className="chunks">
          <summary>Evidenze dal CV ({row.retrieval_chunks.length})</summary>
          <ol>
            {row.retrieval_chunks.map((c) => (
              <li key={`${row.cv_id}-${c.chunk_index}`}>
                <span className="chunk-meta">
                  chunk {c.chunk_index} · score {c.score.toFixed(4)}
                  {c.source ? ` · ${c.source}` : ""}
                </span>
                <pre className="chunk-text">{c.text}</pre>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </article>
  );
}

export function ReportPage() {
  const data = useMemo(() => loadDiscoverReport(), []);

  if (!data) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>Report</h1>
          <p className="muted">Nessun risultato in sessione. Avvia prima un&apos;analisi.</p>
        </header>
        <p>
          <Link to="/">Torna alla job description</Link>
        </p>
      </div>
    );
  }

  const meta = data.meta;
  const warnings = meta?.warnings ?? [];
  const job = data.job_skills;
  const primarySkillsTitle = job.must_have.length > 0 ? "Must-have" : "Richieste";
  const primarySkillsItems = job.must_have.length > 0 ? job.must_have : job.required_skills;

  return (
    <div className="page">
      <header className="page-header spread">
        <div>
          <h1>Report analisi</h1>
          <p className="muted">
            {data.results.length} candidat{data.results.length === 1 ? "o" : "i"} in
            classifica.
          </p>
        </div>
        <Link className="button secondary" to="/">
          Nuova analisi
        </Link>
      </header>

      {warnings.length > 0 ? (
        <div className="banner warn">
          <strong>Avvisi</strong>
          <ul>
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {meta?.retrieval_empty ? (
        <div className="banner warn">
          <strong>Retrieval vuoto</strong> — nessun chunk recuperato; controlla indice e query.
        </div>
      ) : null}

      <section className="card">
        <h2>Skill richieste</h2>
        <div className="jd-skills">
          <TagList title={primarySkillsTitle} items={primarySkillsItems} />
          <TagList title="Nice-to-have" items={job.nice_to_have} />
        </div>
      </section>

      {meta?.latency_ms && Object.keys(meta.latency_ms).length > 0 ? (
        <details className="card muted-block latency-details">
          <summary>Latency (ms)</summary>
          <ul className="kv latency-kv">
            {Object.entries(meta.latency_ms).map(([k, v]) => (
              <li key={k}>
                <span>{k}</span>
                <span>{v.toFixed(0)}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <section className="results">
        {data.results.map((row) => (
          <ResultCard key={row.cv_id} row={row} />
        ))}
      </section>
    </div>
  );
}
