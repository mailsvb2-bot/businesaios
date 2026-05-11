import { useMemo, useState } from "react";

const DEFAULT_API = "https://api.businessaios.ru";
const DEFAULT_EMAIL = "pilot@example.com";
const DEFAULT_INTENT = "pilot";

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

async function postJson(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload)
  });
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

function initialIntakeId() {
  try {
    return new URLSearchParams(window.location.search).get("intake_id") || "";
  } catch {
    return "";
  }
}

export function App() {
  const [apiBase, setApiBase] = useState(DEFAULT_API);
  const [health, setHealth] = useState(null);
  const [readyz, setReadyz] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState(DEFAULT_EMAIL);
  const [intent, setIntent] = useState(DEFAULT_INTENT);
  const [intakeId, setIntakeId] = useState(initialIntakeId());
  const [ctaLoading, setCtaLoading] = useState(false);
  const [ctaResult, setCtaResult] = useState(null);
  const [ctaStatus, setCtaStatus] = useState(null);

  const endpoints = useMemo(() => {
    const base = apiBase.replace(/\/$/, "");
    return {
      health: `${base}/health`,
      readyz: `${base}/readyz`,
      openapi: `${base}/openapi.json`,
      ctaStart: `${base}/public-site/cta/start`,
      ctaStatus: (id) => `${base}/public-site/cta/${encodeURIComponent(id)}`
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

  const startCta = async () => {
    setCtaLoading(true);
    setError("");
    setCtaResult(null);
    try {
      const payload = {
        email: email.trim(),
        source: "landing",
        intent: intent.trim() || DEFAULT_INTENT
      };
      const result = await postJson(endpoints.ctaStart, payload);
      setCtaResult(result);
      if (result?.intake_id) {
        setIntakeId(result.intake_id);
      }
      const uiUrl = result?.next?.ui_url;
      if (uiUrl) {
        window.location.assign(uiUrl);
      }
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setCtaLoading(false);
    }
  };

  const checkCtaStatus = async () => {
    const id = intakeId.trim();
    if (!id) {
      setError("intake_id is required to check CTA status");
      return;
    }
    setCtaLoading(true);
    setError("");
    try {
      const statusPayload = await getJson(endpoints.ctaStatus(id));
      setCtaStatus(statusPayload);
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setCtaLoading(false);
    }
  };

  return (
    <main className="page">
      <section className="hero card">
        <p className="eyebrow">Behavioral Operating System for microbusiness</p>
        <h1>BusinessAIOS Control UI</h1>
        <p className="muted">
          Landing CTA is wired to the public-site intake API. The button records interest and redirects to the app URL returned by the backend.
        </p>
        <div className="cta-form">
          <label>
            Work email
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="founder@example.com"
              type="email"
            />
          </label>
          <label>
            Intent
            <input
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder="pilot"
            />
          </label>
          <button className="primary" onClick={startCta} disabled={ctaLoading}>
            {ctaLoading ? "Starting..." : "Start CTA flow"}
          </button>
        </div>
        {ctaResult ? <pre className="success">{JSON.stringify(ctaResult, null, 2)}</pre> : null}
      </section>

      <section className="card">
        <h2>CTA status check</h2>
        <p className="muted">Use an intake_id from the redirect URL or from the CTA response.</p>
        <input
          value={intakeId}
          onChange={(e) => setIntakeId(e.target.value)}
          placeholder="cta-..."
        />
        <div className="row">
          <button onClick={checkCtaStatus} disabled={ctaLoading || !intakeId.trim()}>
            Check CTA status
          </button>
        </div>
        {ctaStatus ? <pre>{JSON.stringify(ctaStatus, null, 2)}</pre> : null}
      </section>

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
