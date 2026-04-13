import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { postDiscover } from "../api/discover";
import { saveDiscoverReport } from "../storage";

export function HomePage() {
  const navigate = useNavigate();
  const [jobDescription, setJobDescription] = useState("");
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const jd = jobDescription.trim();
    const q = query.trim();
    if (!jd && !q) {
      setError("Inserisci una job description e/o una query di ricerca.");
      return;
    }
    setLoading(true);
    try {
      const data = await postDiscover({
        job_description: jd || undefined,
        query: q,
        top_k: topK,
      });
      saveDiscoverReport(data);
      navigate("/report");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore sconosciuto");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Nuova analisi</h1>
        <p className="muted">
          Incolla la job description. I risultati verranno mostrati
          nella pagina report.
        </p>
      </header>

      <form className="card" onSubmit={onSubmit}>
        <label className="field">
          <span>Job description</span>
          <textarea
            rows={14}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Es. cerchiamo un backend Python con esperienza su FastAPI e PostgreSQL…"
            disabled={loading}
          />
        </label>

        <label className="field">
          <span>Keywords</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Parole chiave (opzionale)"
            disabled={loading}
          />
        </label>

        <label className="field inline">
          <span>Top K candidati</span>
          <input
            type="number"
            min={1}
            max={100}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value) || 20)}
            disabled={loading}
          />
        </label>

        {error ? <p className="error">{error}</p> : null}

        <div className="actions">
          <button type="submit" className="primary" disabled={loading}>
            {loading ? "Analisi in corso…" : "Avvia analisi"}
          </button>
        </div>
      </form>
    </div>
  );
}
