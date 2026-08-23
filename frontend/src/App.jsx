import { useCallback, useEffect, useMemo, useState } from "react";
import { AcquisitionPlanner } from "./AcquisitionPlanner.jsx";

const DEFAULT_API = import.meta.env.VITE_API_BASE || "https://api.businessaios.ru";

const GOALS = [
  { value: "growth", title: "Больше клиентов", text: "Найти потери в воронке и точки роста продаж." },
  { value: "retention", title: "Возвращать клиентов", text: "Находить клиентов, которых стоит реактивировать." },
  { value: "ads_efficiency", title: "Эффективнее реклама", text: "Искать неэффективный расход и проблемы атрибуции." },
  { value: "sales", title: "Сильнее продажи", text: "Показывать зависшие сделки и пропущенные повторные контакты с клиентом." },
  { value: "operations", title: "Меньше рутины", text: "Находить повторяющиеся операции и задержки исполнения." }
];

const AUTONOMY = [
  { value: "advisor", title: "Советник", badge: "Самый безопасный старт", text: "Анализирует бизнес и предлагает действия. Ничего сам не отправляет и не тратит." },
  { value: "assistant", title: "Помощник", badge: "Рекомендуем после знакомства", text: "Автоматизирует безопасные шаги, а важные действия отправляет вам на подтверждение." },
  { value: "autopilot", title: "Автопилот", badge: "После проверки интеграций", text: "Целевой режим автономной работы в заданных лимитах. Включается только после проверок безопасности." }
];

const STEP_LABELS = ["О бизнесе", "Цель", "Интеграции", "Режим"];

const INITIAL_FORM = {
  email: "",
  business_name: "",
  website: "",
  industry: "",
  city: "",
  business_model: "services",
  goal: "growth",
  autonomy_mode: "advisor"
};

async function readResponse(resp) {
  const text = await resp.text();
  let parsed;
  try {
    parsed = text ? JSON.parse(text) : {};
  } catch {
    parsed = { raw: text };
  }
  if (!resp.ok) throw new Error(parsed?.detail || `HTTP ${resp.status}`);
  return parsed;
}

async function getJson(url, headers = {}) {
  return readResponse(await fetch(url, { headers, credentials: "include" }));
}

async function postJson(url, payload, headers = {}) {
  return readResponse(await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(payload),
    credentials: "include"
  }));
}

function initialIntakeId() {
  try {
    return new URLSearchParams(window.location.search).get("intake_id") || "";
  } catch {
    return "";
  }
}

function isValidEmail(value) {
  const email = String(value || "").trim();
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function providerInitial(title) {
  return String(title || "?").trim().slice(0, 2).toUpperCase();
}

function statusClass(item) {
  if (item.availability === "available_read_only") return "ready";
  if (item.availability === "preparing") return "preparing";
  return "roadmap";
}

function connectionIdentityCopy(provider) {
  const key = String(provider?.provider_key || "").toLowerCase();
  if (key.includes("website") || key.includes("wordpress") || key.includes("webflow")) {
    return { label: "Сайт или проект", placeholder: "Например, https://example.ru" };
  }
  if (key.includes("marketplace") || key.includes("ozon") || key.includes("wildberries")) {
    return { label: "Кабинет или магазин", placeholder: "Например, ID кабинета продавца" };
  }
  return { label: "Аккаунт или кабинет", placeholder: "Например, ID аккаунта или адрес кабинета" };
}

function isSuccessfulLiveEvidence(row) {
  return String(row?.mode || "").toLowerCase() === "live"
    && row?.accepted === true
    && String(row?.status || "").toLowerCase() === "live_executed";
}

function Workspace({ data, apiBase, onRestart }) {
  const profile = data.business_profile || {};
  const progress = data.onboarding_progress || {};
  const preview = data.first_value_preview || {};
  const integrations = data.integration_plan || [];
  const ownerSession = data.owner_session || {};
  const apiKey = ownerSession.api_key || "";
  const baseApi = apiBase.replace(/\/$/, "");
  const workspaceUrl = `${baseApi}/business-workspace/providers`;
  const acquisitionUrl = `${baseApi}/business-workspace/acquisition-plan`;
  const authHeaders = useMemo(() => (apiKey ? { "X-API-Key": apiKey } : {}), [apiKey]);
  const selectedKeys = useMemo(() => new Set(integrations.map((item) => item.provider_key)), [integrations]);
  const [catalog, setCatalog] = useState([]);
  const [activeKey, setActiveKey] = useState("");
  const [externalRef, setExternalRef] = useState("");
  const [secrets, setSecrets] = useState({});
  const [historyByProvider, setHistoryByProvider] = useState({});
  const [workspaceLoading, setWorkspaceLoading] = useState(Boolean(apiKey));
  const [workspaceBusy, setWorkspaceBusy] = useState("");
  const [workspaceError, setWorkspaceError] = useState("");
  const [lastAction, setLastAction] = useState(null);

  const refreshCatalog = async () => {
    if (!apiKey) return [];
    const payload = await getJson(workspaceUrl, authHeaders);
    const rows = Array.isArray(payload.providers) ? payload.providers : [];
    setCatalog(rows);
    setActiveKey((current) => {
      if (current && rows.some((row) => row.provider_key === current)) return current;
      return rows.find((row) => selectedKeys.has(row.provider_key) && row.customer_selectable)?.provider_key
        || rows.find((row) => row.customer_selectable)?.provider_key
        || "";
    });
    return rows;
  };

  const loadHistory = async (providerKey) => {
    if (!apiKey || !providerKey) return [];
    const payload = await getJson(`${workspaceUrl}?provider_key=${encodeURIComponent(providerKey)}`, authHeaders);
    const rows = Array.isArray(payload.history) ? payload.history : [];
    setHistoryByProvider((previous) => ({ ...previous, [providerKey]: rows }));
    return rows;
  };

  useEffect(() => {
    if (!apiKey) {
      setWorkspaceLoading(false);
      return;
    }
    let cancelled = false;
    setWorkspaceLoading(true);
    refreshCatalog()
      .then((rows) => Promise.all(rows.filter((row) => selectedKeys.has(row.provider_key) && row.connected).map((row) => loadHistory(row.provider_key))))
      .catch(() => {
        if (!cancelled) setWorkspaceError("Не удалось открыть защищённый список подключений. Проверьте соединение и повторите попытку.");
      })
      .finally(() => {
        if (!cancelled) setWorkspaceLoading(false);
      });
    return () => { cancelled = true; };
  }, [apiKey]);

  const providers = catalog
    .filter((row) => selectedKeys.size === 0 || selectedKeys.has(row.provider_key))
    .sort((left, right) => Number(Boolean(right.connected)) - Number(Boolean(left.connected)));
  const activeProvider = providers.find((row) => row.provider_key === activeKey) || providers[0] || null;
  const evidenceRows = Object.values(historyByProvider).flatMap((rows) => rows || []);
  const liveEvidence = evidenceRows.find(isSuccessfulLiveEvidence) || null;
  const connected = providers.some((row) => row.connected);
  const baseCompleted = Math.min(Number(progress.completed || 0), 4);
  const verifiedCompleted = Math.min(6, baseCompleted + (connected ? 1 : 0) + (liveEvidence ? 1 : 0));
  const verifiedPercent = Math.round((verifiedCompleted / 6) * 100);
  const evidenceProvider = liveEvidence ? catalog.find((row) => row.provider_key === liveEvidence.provider_key) : null;
  const resourceCount = liveEvidence?.parsed_response?.resource_count ?? liveEvidence?.transport_response?.resource_count;
  const identityCopy = connectionIdentityCopy(activeProvider);

  const runWorkspaceAction = async (name, payload, providerKey = activeProvider?.provider_key) => {
    if (!providerKey) return null;
    setWorkspaceBusy(name);
    setWorkspaceError("");
    try {
      const result = await postJson(workspaceUrl, { provider_key: providerKey, ...payload }, authHeaders);
      setLastAction({ name, providerKey, result });
      await refreshCatalog();
      if (name === "sync") await loadHistory(providerKey);
      return result;
    } catch {
      setWorkspaceError("Действие не выполнено. Проверьте подключение и повторите попытку.");
      return null;
    } finally {
      setWorkspaceBusy("");
    }
  };

  const activateProvider = async () => {
    if (!activeProvider) return;
    const requiredMissing = (activeProvider.secret_fields || []).some((field) => field.required && !String(secrets[field.secret_name] || "").trim());
    if (!externalRef.trim() || requiredMissing) {
      setWorkspaceError("Укажите аккаунт и заполните обязательные поля доступа.");
      return;
    }
    const result = await runWorkspaceAction("activate", { action: "activate", external_ref: externalRef.trim(), secrets });
    if (result) {
      setSecrets({});
      await loadHistory(activeProvider.provider_key).catch(() => []);
    }
  };

  const probeProvider = async () => {
    await runWorkspaceAction("probe", { action: "read", mode: "live" });
  };

  const syncProvider = async () => {
    if (!activeProvider) return;
    const operation = activeProvider.runtime_plan?.read_operations?.[0];
    if (!operation) {
      setWorkspaceError("Для этого источника пока нет доступной операции чтения. Сначала проверьте подключение.");
      return;
    }
    await runWorkspaceAction("sync", { action: "read", mode: "live", operation, payload: {} });
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/"><span className="brand-mark">B</span><span className="brand-name">BusinessAIOS</span></a>
        <div className="topbar-actions"><span className="safe-chip"><span className="safe-chip-full">Безопасный режим · чтение данных</span><span className="safe-chip-short">Режим чтения</span></span><button className="ghost small" onClick={onRestart}>Новый бизнес</button></div>
      </header>

      <section className="workspace-hero">
        <div>
          <p className="eyebrow">Кабинет бизнеса</p>
          <h1>{profile.name || "Ваш бизнес"}</h1>
          <p className="lead">{liveEvidence ? "Первые реальные данные уже подтверждены. Ниже — результат и следующие безопасные действия." : "Сейчас задача одна: получить первый подтверждённый результат на ваших данных. Никаких отправок, изменений или расходов."}</p>
        </div>
        <div className="progress-card">
          <div className="progress-head"><span>До рабочего результата</span><strong>{verifiedPercent}%</strong></div>
          <div className="progress-track" role="progressbar" aria-label="Готовность подключения" aria-valuemin={0} aria-valuemax={100} aria-valuenow={verifiedPercent}><span style={{ width: `${verifiedPercent}%` }} /></div>
          <small>{liveEvidence ? "Первый подтверждённый результат получен." : connected ? "Источник подключён. Осталось получить первые данные." : "Следующий шаг: подключить выбранный источник."}</small>
        </div>
      </section>

      <section className="summary-grid">
        <article className="summary-card"><span className="summary-icon">◎</span><div><small>Цель</small><strong>{GOALS.find((goal) => goal.value === profile.goal)?.title || profile.goal || "Рост"}</strong></div></article>
        <article className="summary-card"><span className="summary-icon">⌁</span><div><small>Источники</small><strong>{providers.filter((row) => row.connected).length} подключено / {integrations.length} выбрано</strong></div></article>
        <article className="summary-card"><span className="summary-icon">◇</span><div><small>Режим</small><strong>{data.user_functionality?.autonomy_mode_label || "Советник"}</strong></div></article>
      </section>

      <section className="panel first-value-panel" aria-live="polite">
        <div className="panel-title-row">
          <div><p className="eyebrow">{liveEvidence ? "Подтверждено на ваших данных" : connected ? "Один шаг до результата" : "Первый полезный результат"}</p><h2>{liveEvidence ? "Первые реальные данные получены" : preview.title || "Первый полезный результат"}</h2></div>
          <span className={`result-badge ${liveEvidence ? "verified" : "pending"}`}>{liveEvidence ? "Данные подтверждены" : connected ? "Готово к чтению" : "Нужно подключение"}</span>
        </div>
        <p className="muted-text">{liveEvidence ? `${evidenceProvider?.title || liveEvidence.provider_key || "Источник"}: BusinessAIOS подтвердил чтение реальных данных и теперь может опираться на факты.` : connected ? "Подключение уже сохранено. Нажмите «Получить первые данные» у источника — подтверждённый результат появится здесь." : preview.message}</p>
        <div className="check-list compact-check-list">
          {liveEvidence ? (
            <>
              <div className="check-row"><span>✓</span><strong>Подключение работает</strong></div>
              <div className="check-row"><span>✓</span><strong>Данные прочитаны в безопасном режиме</strong></div>
              {resourceCount !== undefined ? <div className="check-row"><span>✓</span><strong>Получено объектов: {resourceCount}</strong></div> : null}
            </>
          ) : (preview.checks || []).map((item) => <div className="check-row" key={item}><span>→</span><strong>{item}</strong></div>)}
        </div>
        <div className="truth-note">{liveEvidence ? "Это не прогноз и не демонстрационные данные: результат подтверждён реальным чтением из подключённого источника." : "До первого чтения здесь нет финансовых обещаний или выдуманных выводов. Сначала факты — потом рекомендации."}</div>
      </section>

      <section className="workspace-grid">
        <article className="panel primary-panel">
          <div className="panel-title-row"><div><p className="eyebrow">Шаг к результату</p><h2>Подключите источник данных</h2></div><span className="privacy-badge">Только чтение</span></div>
          <p className="muted-text">Выберите источник и дайте доступ для чтения. Секреты используются только для подключения и не сохраняются в браузере.</p>

          {!apiKey ? <div className="error-box inline-error" role="alert">Не удалось восстановить защищённый вход в этот кабинет. Данные доступа в браузере не хранятся; создайте новый кабинет, если защищённая сессия уже истекла.</div> : null}
          {workspaceLoading ? <div className="loading-box">Восстанавливаем кабинет и проверяем подключения…</div> : null}
          {workspaceError ? <div className="error-box inline-error" role="alert">{workspaceError}</div> : null}

          <div className="connection-list">
            {providers.length ? providers.map((item) => (
              <button type="button" className={`connection-row ${activeProvider?.provider_key === item.provider_key ? "selected" : ""}`} aria-current={activeProvider?.provider_key === item.provider_key ? "true" : undefined} onClick={() => { setActiveKey(item.provider_key); setExternalRef(""); setSecrets({}); }} key={item.provider_key} disabled={!item.customer_selectable}>
                <div className="provider-logo">{providerInitial(item.title)}</div>
                <div className="connection-copy"><strong>{item.title}</strong><span>{item.connected ? "Подключено для чтения" : item.customer_selectable ? "Можно подключить" : "Пока не доступно"}</span></div>
                <span className={`dot ${item.connected ? "green" : item.customer_selectable ? "orange" : "gray"}`} />
              </button>
            )) : <p className="empty-state">Для выбранных источников пока нет готового подключения.</p>}
          </div>

          {activeProvider && apiKey ? (
            <div className="connection-flow">
              <div className="connection-steps" aria-label="Этапы подключения">
                <span className="done">1. Источник выбран</span>
                <span className={activeProvider.connected ? "done" : "active"}>2. Доступ</span>
                <span className={liveEvidence?.provider_key === activeProvider.provider_key ? "done" : activeProvider.connected ? "active" : ""}>3. Первые данные</span>
              </div>
              <div className="step-content workspace-step-content">
                <div className="section-heading"><h2>{activeProvider.title}</h2><p>{activeProvider.connected ? "Доступ сохранён. Получите первые данные — это главное действие сейчас." : "Нужен только доступ для чтения. Изменения во внешней системе остаются выключены."}</p></div>
                {!activeProvider.connected ? (
                  <div className="form-grid">
                    <label className="full">{identityCopy.label}<input value={externalRef} onChange={(event) => setExternalRef(event.target.value)} placeholder={identityCopy.placeholder} /><small className="input-help">Это идентификатор именно вашего кабинета или проекта — не внутренний ID BusinessAIOS.</small></label>
                    {(activeProvider.secret_fields || []).map((field) => (
                      <label className={field.multiline ? "full" : ""} key={field.secret_name}>{field.label}{field.multiline ? <textarea value={secrets[field.secret_name] || ""} onChange={(event) => setSecrets((previous) => ({ ...previous, [field.secret_name]: event.target.value }))} placeholder={field.placeholder || ""} /> : <input type="password" autoComplete="off" value={secrets[field.secret_name] || ""} onChange={(event) => setSecrets((previous) => ({ ...previous, [field.secret_name]: event.target.value }))} placeholder={field.placeholder || ""} />}</label>
                    ))}
                    <button type="button" className="primary" disabled={Boolean(workspaceBusy)} onClick={activateProvider}>{workspaceBusy === "activate" ? "Сохраняем доступ…" : "Подключить для чтения"}</button>
                  </div>
                ) : (
                  <div className="navigation-row workspace-actions">
                    <button type="button" className="ghost" disabled={Boolean(workspaceBusy)} onClick={probeProvider}>{workspaceBusy === "probe" ? "Проверяем…" : "Проверить доступ"}</button>
                    <button type="button" className="primary" disabled={Boolean(workspaceBusy)} onClick={syncProvider}>{workspaceBusy === "sync" ? "Получаем данные…" : "Получить первые данные"}</button>
                  </div>
                )}
                <small className="helper-text">BusinessAIOS сейчас может только читать. Сообщения, публикации, расходы и другие изменения выключены.</small>
                {lastAction?.providerKey === activeProvider.provider_key ? <details className="technical-inline"><summary>Технические детали последней операции</summary><pre>{JSON.stringify(lastAction.result, null, 2)}</pre></details> : null}
              </div>
            </div>
          ) : null}
        </article>

        <article className="panel next-step-panel">
          <p className="eyebrow">Что дальше</p>
          <h2>{liveEvidence ? "Переходите от настройки к решениям" : connected ? "Получите факты одним действием" : "Сначала одно подключение"}</h2>
          <p className="muted-text">{liveEvidence ? "Источник уже дал реальные данные. Теперь сценарный расчёт ниже можно сопоставлять с фактическими показателями бизнеса." : connected ? "Доступ уже есть. Не заполняйте ничего лишнего — получите первые данные и посмотрите подтверждённый результат выше." : "Не нужно настраивать всю систему. Достаточно подключить один выбранный источник и получить первый результат."}</p>
          <div className="check-list">
            <div className="check-row"><span>{connected ? "✓" : "1"}</span><strong>Подключить один источник</strong></div>
            <div className="check-row"><span>{liveEvidence ? "✓" : "2"}</span><strong>Получить первые реальные данные</strong></div>
            <div className="check-row"><span>3</span><strong>Сравнить факты со сценарием и выбрать действие</strong></div>
          </div>
        </article>
      </section>

      <AcquisitionPlanner enabled={Boolean(apiKey)} onEvaluate={(payload) => postJson(acquisitionUrl, payload, authHeaders)} />

      <section className="panel business-card">
        <div><p className="eyebrow">Профиль</p><h2>{profile.name || "Бизнес"}</h2></div>
        <div className="business-meta">{profile.industry ? <span>{profile.industry}</span> : null}{profile.city ? <span>{profile.city}</span> : null}{profile.website ? <a href={profile.website} target="_blank" rel="noreferrer">{profile.website}</a> : null}</div>
      </section>

      <details className="diagnostics"><summary>Техническая информация</summary><pre>{JSON.stringify({ intake_id: data.intake_id, tenant_id: data.tenant_id, business_id: data.business_id, status: data.onboarding_status, owner_session_expires_at: ownerSession.expires_at || null, live_sync_evidence: liveEvidence || null }, null, 2)}</pre></details>
    </main>
  );
}

export function App() {
  const [apiBase] = useState(DEFAULT_API);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [marketLoading, setMarketLoading] = useState(true);
  const [error, setError] = useState("");
  const [marketError, setMarketError] = useState("");
  const [marketplace, setMarketplace] = useState([]);
  const [selectedProviders, setSelectedProviders] = useState([]);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState(() => ({ ...INITIAL_FORM }));

  const endpoints = useMemo(() => {
    const base = apiBase.replace(/\/$/, "");
    return { integrations: `${base}/public-site/integrations`, ctaStart: `${base}/public-site/cta/start`, ctaStatus: (id) => `${base}/public-site/cta/${encodeURIComponent(id)}` };
  }, [apiBase]);

  const loadMarketplace = useCallback(async () => {
    setMarketLoading(true);
    setMarketError("");
    try {
      const payload = await getJson(endpoints.integrations);
      setMarketplace(Array.isArray(payload.items) ? payload.items : []);
    } catch {
      setMarketplace([]);
      setMarketError("Не удалось загрузить список интеграций. Проверьте соединение и повторите попытку.");
    } finally {
      setMarketLoading(false);
    }
  }, [endpoints.integrations]);

  useEffect(() => {
    void loadMarketplace();
  }, [loadMarketplace]);

  useEffect(() => {
    const intakeId = initialIntakeId();
    if (!intakeId) return;
    let cancelled = false;
    setLoading(true);
    getJson(endpoints.ctaStatus(intakeId))
      .then((payload) => { if (!cancelled && payload.ok) setResult(payload); })
      .catch(() => { if (!cancelled) setError("Не удалось открыть сохранённый кабинет бизнеса."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [endpoints]);

  const emailValid = isValidEmail(form.email);
  const updateForm = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));
  const toggleProvider = (item) => {
    if (!item.selectable) return;
    setSelectedProviders((prev) => prev.includes(item.provider_key) ? prev.filter((key) => key !== item.provider_key) : [...prev, item.provider_key]);
  };
  const canContinue = () => {
    if (step === 0) return Boolean(form.business_name.trim() && emailValid);
    if (step === 1) return Boolean(form.goal);
    if (step === 2) return selectedProviders.length > 0;
    return Boolean(form.autonomy_mode);
  };

  const finishOnboarding = async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await postJson(endpoints.ctaStart, { ...form, selected_providers: selectedProviders, intent: form.goal, source: "businessaios_product_onboarding", requested_surface: "business_workspace" });
      setResult(payload);
      if (payload.intake_id) window.history.replaceState(null, "", `?intake_id=${encodeURIComponent(payload.intake_id)}`);
    } catch {
      setError("Не удалось создать кабинет. Проверьте соединение и повторите попытку.");
    } finally {
      setLoading(false);
    }
  };

  const restart = () => {
    window.history.replaceState(null, "", window.location.pathname);
    setResult(null);
    setStep(0);
    setSelectedProviders([]);
    setForm({ ...INITIAL_FORM });
    setError("");
  };

  if (result) return <Workspace data={result} apiBase={apiBase} onRestart={restart} />;

  return (
    <main className="onboarding-shell">
      <header className="topbar onboarding-topbar"><div className="brand"><span className="brand-mark">B</span><span className="brand-name">BusinessAIOS</span></div><span className="topbar-note">Настройка бизнеса</span></header>
      <section className="onboarding-layout">
        <aside className="intro-column">
          <p className="eyebrow">Управление бизнесом с ИИ</p><h1>Подключите бизнес.<br />Остальное система разберёт сама.</h1>
          <p className="lead">Сначала только чтение и анализ. Никаких расходов, сообщений клиентам или публикаций без вашего разрешения.</p>
          <div className="trust-list">
            <div><span>✓</span><p><strong>Безопасный старт</strong><small>Ничего не отправляем и не меняем без вашего разрешения.</small></p></div>
            <div><span>✓</span><p><strong>Честные статусы</strong><small>Показываем только реально доступные интеграции.</small></p></div>
            <div><span>✓</span><p><strong>Первый результат на ваших данных</strong><small>Без выдуманных финансовых обещаний.</small></p></div>
          </div>
        </aside>

        <section className="onboarding-card">
          <div className="stepper">{STEP_LABELS.map((label, index) => <div className={`step ${index === step ? "active" : ""} ${index < step ? "done" : ""}`} aria-current={index === step ? "step" : undefined} key={label}><span>{index < step ? "✓" : index + 1}</span><small>{label}</small></div>)}</div>

          {step === 0 ? <div className="step-content"><div className="section-heading"><p className="eyebrow">Шаг 1</p><h2>Расскажите о бизнесе</h2><p>Этого достаточно, чтобы создать отдельный защищённый кабинет.</p></div><div className="form-grid"><label className="full">Название бизнеса<input value={form.business_name} onChange={updateForm("business_name")} placeholder="Например, Студия Линия" autoFocus /></label><label>Email владельца<input value={form.email} onChange={updateForm("email")} placeholder="you@company.ru" type="email" aria-invalid={Boolean(form.email.trim()) && !emailValid} aria-describedby={form.email.trim() && !emailValid ? "owner-email-error" : undefined} />{form.email.trim() && !emailValid ? <small className="field-error" id="owner-email-error">Введите email в формате name@company.ru</small> : null}</label><label>Сайт или страница<input value={form.website} onChange={updateForm("website")} placeholder="https://..." /></label><label>Сфера<input value={form.industry} onChange={updateForm("industry")} placeholder="Услуги, магазин, образование..." /></label><label>Город<input value={form.city} onChange={updateForm("city")} placeholder="Москва" /></label><label className="full">Модель бизнеса<select value={form.business_model} onChange={updateForm("business_model")}><option value="services">Услуги</option><option value="commerce">Товары / интернет-магазин</option><option value="marketplace">Маркетплейсы</option><option value="b2b">B2B</option><option value="mixed">Смешанная</option></select></label></div></div> : null}

          {step === 1 ? <div className="step-content"><div className="section-heading"><p className="eyebrow">Шаг 2</p><h2>Что важнее прямо сейчас?</h2><p>BusinessAIOS начнёт анализ с выбранной бизнес-задачи.</p></div><div className="choice-grid">{GOALS.map((goal) => <button type="button" className={`choice-card ${form.goal === goal.value ? "selected" : ""}`} aria-pressed={form.goal === goal.value} onClick={() => setForm((prev) => ({ ...prev, goal: goal.value }))} key={goal.value}><span className="radio-dot" /><strong>{goal.title}</strong><small>{goal.text}</small></button>)}</div></div> : null}

          {step === 2 ? <div className="step-content integrations-step"><div className="section-heading"><p className="eyebrow">Шаг 3</p><h2>Где уже живут данные бизнеса?</h2><p>Выберите хотя бы один источник. Подключение начнётся в режиме только чтения.</p></div>{marketLoading ? <div className="loading-box">Загружаем доступные интеграции…</div> : null}{marketError && !marketLoading ? <div className="recovery-box" role="alert"><p>{marketError}</p><button type="button" className="ghost" onClick={loadMarketplace}>Повторить загрузку</button></div> : null}<div className="integration-grid">{marketplace.map((item) => { const selected = selectedProviders.includes(item.provider_key); return <button type="button" disabled={!item.selectable} className={`integration-card ${selected ? "selected" : ""} ${!item.selectable ? "disabled" : ""}`} aria-pressed={selected} onClick={() => toggleProvider(item)} key={item.provider_key}><div className="integration-card-head"><span className="provider-logo">{providerInitial(item.title)}</span>{item.recommended ? <span className="recommended">Рекомендуем</span> : null}</div><strong>{item.title}</strong><small>{item.description}</small><span className={`status-pill ${statusClass(item)}`}>{selected ? "Выбрано ✓" : item.availability_label}</span></button>; })}</div><p className="selection-count" aria-live="polite">Выбрано: <strong>{selectedProviders.length}</strong></p></div> : null}

          {step === 3 ? <div className="step-content"><div className="section-heading"><p className="eyebrow">Шаг 4</p><h2>Сколько свободы дать системе?</h2><p>На старте система всё равно ничего не отправит и не изменит без проверки.</p></div><div className="autonomy-grid">{AUTONOMY.map((mode) => <button type="button" className={`autonomy-card ${form.autonomy_mode === mode.value ? "selected" : ""}`} aria-pressed={form.autonomy_mode === mode.value} onClick={() => setForm((prev) => ({ ...prev, autonomy_mode: mode.value }))} key={mode.value}><span className="mode-badge">{mode.badge}</span><strong>{mode.title}</strong><small>{mode.text}</small></button>)}</div><div className="launch-preview"><span>✓</span><div><strong>После создания кабинета</strong><p>Вы подключите один источник, получите первые реальные данные и сразу увидите подтверждённый результат.</p></div></div></div> : null}

          {error ? <div className="error-box" role="alert">{error}</div> : null}
          <div className="navigation-row"><button type="button" className="ghost" disabled={step === 0 || loading} onClick={() => setStep((value) => Math.max(0, value - 1))}>Назад</button>{step < STEP_LABELS.length - 1 ? <button type="button" className="primary" disabled={!canContinue() || loading} onClick={() => setStep((value) => Math.min(STEP_LABELS.length - 1, value + 1))}>Продолжить →</button> : <button type="button" className="primary launch" disabled={!canContinue() || loading} onClick={finishOnboarding}>{loading ? "Создаём кабинет…" : "Создать мой BusinessAIOS →"}</button>}</div>
        </section>
      </section>
      <footer className="product-footer">BusinessAIOS · безопасная автоматизация бизнеса · изменения и отправки только после проверки</footer>
    </main>
  );
}

export { getJson, postJson, isSuccessfulLiveEvidence };
