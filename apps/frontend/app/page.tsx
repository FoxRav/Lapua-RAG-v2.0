"use client";

import { FormEvent, useState } from "react";

type SourceRef = {
  doc_id: string;
  toimielin: string;
  poytakirja_pvm: string | null;
  pykala_nro: string | null;
  otsikko: string | null;
  score: number;
};

type AnswerResponse = {
  answer: string;
  sources: SourceRef[];
  strategy_used: string;
  model?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function HomePage() {
  const [question, setQuestion] = useState<string>("Simpsiönvuori Oy takaus");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Backend error ${res.status}: ${text}`);
      }

      const data: AnswerResponse = await res.json();
      setAnswer(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <section className="panel panel-main">
        <h1 className="panel-title">Lapuan päätösten kysely</h1>
        <p className="panel-description">
          Kysy Simpsiönvuoresta, taloudesta tai muista päätöksistä. Agentti hakee parhaiten vastaavat
          pykälät ja muodostaa yhteenvedon.
        </p>
        <form className="query-form" onSubmit={handleSubmit}>
          <label className="field">
            <span className="field-label">Kysymys</span>
            <textarea
              className="field-input field-textarea"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={4}
              placeholder="Mitä päätöksiä Simpsiönvuori Oy:n takauksista ja lainoista on tehty?"
            />
          </label>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Haetaan vastauksia..." : "Hae"}
          </button>
        </form>

        {error && <div className="alert alert-error">Virhe: {error}</div>}
      </section>

      <section className="panel panel-answer">
        <h2 className="panel-title">Vastaus</h2>
        {!answer && !loading && <p className="muted">Tee kysymys vasemmalta.</p>}
        {loading && <p className="muted">Haetaan päätöksiä ja muodostetaan vastausta...</p>}
        {answer && (
          <>
            <div className="answer-text" dangerouslySetInnerHTML={{ __html: answer.answer }} />
            <div className="answer-meta">
              <span>Strategia: {answer.strategy_used}</span>
              {answer.model && <span>Malli: {answer.model}</span>}
            </div>
          </>
        )}
      </section>

      {answer && answer.sources.length > 0 && (
        <section className="panel panel-sources">
          <h2 className="panel-title">Lähdepykälät</h2>
          <ul className="source-list">
            {answer.sources.map((s, idx) => (
              <li key={`${s.doc_id}-${s.pykala_nro}-${idx}`} className="source-item">
                <div className="source-header">
                  <span className="source-pill">
                    {s.toimielin} • {s.poytakirja_pvm ?? "?"} • {s.pykala_nro ?? "§ ?"}
                  </span>
                  <span className="source-score">score {s.score.toFixed(3)}</span>
                </div>
                {s.otsikko && <div className="source-title">{s.otsikko}</div>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}


