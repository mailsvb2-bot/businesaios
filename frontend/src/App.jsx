import { useMemo, useState } from "react";

const DEFAULT_API = "https://api.businessaios.ru";

async function getJson(url) {
  const resp = await fetch(url);
  const text = await resp.text();
  let parsed;
  try {
    parsed = text ? JSON.parse(text) : {};
  } catch {
    parsed = { raw: text };
  }
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${JSON.stringify(parsed)}`);
  }
  return parsed;
}

export function App() {
  const [apiBase, setApiBase] = useState(DEFAULT_API);
  const [health, setHealth] = useState(null);
  const [readyz, setReadyz] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const endpoints = useMemo(() => {
    const base = apiBase.replace(/\/$/, "");
    return {
      health: `${base}/health`,
      readyz: `${base}/readyz`,
      openapi: `${base}/openapi.json`
    };
  }, [apiBase]);

  const runProbe = async () => {
    setLoading(true);
    setError("");
    try {
      const [h, r] = await Promise.all([
        getJson(endpoints.health),
        getJson(endpoints.readyz)
      ]);
      setHealth(h);
      setReadyz(r);
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page">
      <h1>BusinessAIOS Control UI</h1>
      <p className="muted">Staging UI: health/readiness probes + OpenAPI link.</p>

      <section className="card">
        <label>API Base URL</label>
        <input
          value={apiBase}
          onChange={(e) => setApiBase(e.target.value)}
          placeholder="https://api.businessaios.ru"
        />
        <div className="row">
          <button onClick={runProbe} disabled={loading}>
            {loading ? "Checking..." : "Run probes"}
          </button>
          <a href={endpoints.openapi} target="_blank" rel="noreferrer">
            Open OpenAPI
          </a>
        </div>
        {error ? <pre className="error">{error}</pre> : null}
      </section>

      <section className="grid">
        <article className="card">
          <h2>/health</h2>
          <pre>{JSON.stringify(health, null, 2)}</pre>
        </article>
        <article className="card">
          <h2>/readyz</h2>
          <pre>{JSON.stringify(readyz, null, 2)}</pre>
        </article>
      </section>
    </main>
  );
}
