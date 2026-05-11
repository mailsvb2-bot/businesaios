import { useEffect, useMemo, useState } from "react";

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

export function App() {
  const [apiBase, setApiBase] = useState(DEFAULT_API);
  const [health, setHealth] = useState(null);
  const [readyz, setReadyz] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ctaLoading, setCtaLoading] = useState(false);
  const [error, setError] = useState("");
  const [ctaError, setCtaError] = useState("");
  const [ctaResult, setCtaResult] = useState(null);
  const [form, setForm] = useState({
    email: "",
    business_name: "",
    website: "",
    intent: "pilot"
  });

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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const intakeId = params.get("intake_id");
    if (!intakeId) return;
    let cancelled = false;
    getJson(endpoints.ctaStatus(intakeId))
      .then((data) => {
        if (!cancelled) setCtaResult(data);
      })
      .catch((e) => {
        if (!cancelled) setCtaError(String(e?.message || e));
      });
    return () => {
      cancelled = true;
    };
  }, [endpoints]);

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

  const submitCta = async (event) => {
    event.preventDefault();
    setCtaLoading(true);
    setCtaError("");
    try {
      const payload = {
        ...form,
        source: "businessaios_frontend",
        requested_surface: "advisory_onboarding_workspace"
      };
      const data = await postJson(endpoints.ctaStart, payload);
      setCtaResult(data);
      if (data?.next?.ui_url) {
        const nextUrl = new URL(data.next.ui_url, window.location.origin);
        if (nextUrl.searchParams.get("intake_id")) {
          window.history.replaceState(null, "", `?intake_id=${nextUrl.searchParams.get("intake_id")}`);
        }
      }
    } catch (e) {
      setCtaError(String(e?.message || e));
    } finally {
      setCtaLoading(false);
    }
  };

  const updateForm = (key) => (event) => {
    setForm((prev) => ({ ...prev, [key]: event.target.value }));
  };

  return (
    <main className="page">
      <h1>BusinessAIOS Control UI</h1>
      <p className="muted">Staging UI: public CTA onboarding, health/readiness probes, and OpenAPI link.</p>

      <section className="card hero-card">
        <p className="eyebrow">Public landing → advisory workspace</p>
        <h2>Start a BusinessAIOS pilot</h2>
        <p className="muted">
          This creates a read-only advisory intake. Write actions, customer messages, publications, and spend remain blocked until operator review and approvals.
        </p>
        <form className="stack" onSubmit={submitCta}>
          <label>Email</label>
          <input value={form.email} onChange={updateForm("email")} placeholder="owner@example.com" />
          <label>Business name</label>
          <input value={form.business_name} onChange={updateForm("business_name")} placeholder="Your business" />
          <label>Website or channel</label>
          <input value={form.website} onChange={updateForm("website")} placeholder="https://example.com" />
          <label>Intent</label>
          <select value={form.intent} onChange={updateForm("intent")}>
            <option value="pilot">Pilot / advisory onboarding</option>
            <option value="connectors">Connect read-only data sources</option>
            <option value="autopilot">Explore approval-gated autopilot</option>
          </select>
          <button type="submit" disabled={ctaLoading}>
            {ctaLoading ? "Creating intake..." : "Create advisory workspace"}
          </button>
        </form>
        {ctaError ? <pre className="error">{ctaError}</pre> : null}
      </section>

      {ctaResult ? (
        <section className="grid">
          <article className="card">
            <h2>Workspace</h2>
            <p><strong>Intake:</strong> {ctaResult.intake_id}</p>
            <p><strong>Status:</strong> {ctaResult.onboarding_status || ctaResult.measurable_outcome}</p>
            <p><strong>Tenant:</strong> {ctaResult.tenant_id || ctaResult.user_functionality?.tenant_id || "pending"}</p>
            <p><strong>Business:</strong> {ctaResult.business_id || ctaResult.user_functionality?.business_id || "pending"}</p>
            <p><strong>User:</strong> {ctaResult.user_id || ctaResult.user_functionality?.user_id || "pending"}</p>
          </article>
          <article className="card">
            <h2>Safety</h2>
            <p><strong>Write actions:</strong> {String(ctaResult.write_actions_enabled ?? false)}</p>
            <p><strong>Approval required:</strong> {String(ctaResult.approval_required_before_execution ?? true)}</p>
            <p><strong>Admin surface:</strong> {ctaResult.admin_visibility?.surface || "control-plane pending"}</p>
          </article>
          <article className="card wide">
            <h2>Next actions</h2>
            <ul>
              {(ctaResult.next_actions || []).map((item) => (
                <li key={item.code || item.label}>
                  <strong>{item.label || item.code}</strong>
                  {item.provider_lifecycle_stage ? ` — ${item.provider_lifecycle_stage}` : ""}
                </li>
              ))}
            </ul>
            <pre>{JSON.stringify(ctaResult.user_functionality || ctaResult, null, 2)}</pre>
          </article>
        </section>
      ) : null}

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
