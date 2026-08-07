import { useEffect, useMemo, useState } from "react";

const DEFAULT_API = "https://api.businessaios.ru";
const DEFAULT_INTENT = "pilot";

const FALLBACK_PROVIDERS = [
  { provider_key: "telegram_bot", title: "Telegram", domain: "communications", description: "Бот, обращения и сообщения", secret_fields: [{ field_key: "bot_token", label: "Bot Token", placeholder: "123456:ABC...", required: true }] },
  { provider_key: "whatsapp_cloud", title: "WhatsApp", domain: "communications", description: "WhatsApp Business Cloud", secret_fields: [{ field_key: "access_token", label: "Access Token", placeholder: "EAAB...", required: true }, { field_key: "phone_number_id", label: "Phone Number ID", placeholder: "1234567890", required: true }] },
  { provider_key: "generic_website", title: "Сайт", domain: "website", description: "Формы, лиды и web-канал", secret_fields: [{ field_key: "webhook_secret", label: "Webhook Secret", placeholder: "site-webhook-secret", required: true }, { field_key: "admin_api_key", label: "Admin API Key", placeholder: "необязательно", required: false }] },
  { provider_key: "wordpress", title: "WordPress", domain: "website", description: "Сайт и контент WordPress", secret_fields: [{ field_key: "application_password", label: "Application Password", placeholder: "xxxx xxxx xxxx", required: true }, { field_key: "webhook_secret", label: "Webhook Secret", placeholder: "необязательно", required: false }] },
  { provider_key: "shopify", title: "Shopify", domain: "commerce", description: "Товары, заказы и магазин", secret_fields: [{ field_key: "admin_access_token", label: "Admin Access Token", placeholder: "shpat_...", required: true }, { field_key: "webhook_secret", label: "Webhook Secret", placeholder: "shopify-webhook-secret", required: true }] },
  { provider_key: "woocommerce", title: "WooCommerce", domain: "commerce", description: "Каталог и заказы WooCommerce", secret_fields: [{ field_key: "consumer_key", label: "Consumer Key", placeholder: "ck_...", required: true }, { field_key: "consumer_secret", label: "Consumer Secret", placeholder: "cs_...", required: true }, { field_key: "store_url", label: "Адрес магазина", placeholder: "https://shop.example.com", required: true }] },
  { provider_key: "hubspot", title: "HubSpot", domain: "crm", description: "CRM, контакты и сделки", secret_fields: [{ field_key: "private_app_token", label: "Private App Token", placeholder: "pat-...", required: true }] },
  { provider_key: "google_ads", title: "Google Ads", domain: "ads", description: "Рекламные кампании и аналитика", secret_fields: [{ field_key: "developer_token", label: "Developer Token", placeholder: "developer-token", required: true }, { field_key: "refresh_token", label: "Refresh Token", placeholder: "1//...", required: true }, { field_key: "client_id", label: "Client ID", placeholder: "client-id.apps.googleusercontent.com", required: true }, { field_key: "client_secret", label: "Client Secret", placeholder: "client-secret", required: true }] },
  { provider_key: "meta_ads", title: "Meta Ads", domain: "ads", description: "Реклама Meta — пока ограниченный режим", secret_fields: [{ field_key: "access_token", label: "Access Token", placeholder: "EAAB...", required: true }, { field_key: "account_id", label: "Ad Account ID", placeholder: "act_123456", required: true }] },
  { provider_key: "ozon_marketplace", title: "Ozon", domain: "marketplace", description: "Маркетплейс Ozon", secret_fields: [{ field_key: "client_id", label: "Client ID", placeholder: "ozon-client-id", required: true }, { field_key: "api_key", label: "API Key", placeholder: "ozon-api-key", required: true }] },
  { provider_key: "wildberries_marketplace", title: "Wildberries", domain: "marketplace", description: "Маркетплейс Wildberries", secret_fields: [{ field_key: "api_token", label: "API Token", placeholder: "wb-token", required: true }] }
];

const DOMAIN_LABELS = {
  communications: "Общение с клиентами",
  website: "Сайт",
  commerce: "Интернет-магазин",
  marketplace: "Маркетплейсы",
  crm: "CRM",
  ads: "Реклама"
};

async function getJson(url) {
  const resp = await fetch(url);
  const text = await resp.text();
  let parsed;
  try { parsed = text ? JSON.parse(text) : {}; } catch { parsed = { raw: text }; }
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${JSON.stringify(parsed)}`);
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
  try { parsed = text ? JSON.parse(text) : {}; } catch { parsed = { raw: text }; }
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${JSON.stringify(parsed)}`);
  return parsed;
}

function initialIntakeId() {
  try { return new URLSearchParams(window.location.search).get("intake_id") || ""; }
  catch { return ""; }
}

function normalizeProviderCatalog(payload) {
  const rows = Array.isArray(payload) ? payload : payload?.providers || payload?.rows || payload?.items || [];
  if (!Array.isArray(rows) || !rows.length) return FALLBACK_PROVIDERS;
  return rows
    .filter((item) => item && item.provider_key && item.domain !== "platform_infra")
    .map((item) => ({
      ...item,
      title: item.title || item.display_name || item.provider_key,
      description: item.description || "Подключение источника данных",
      secret_fields: Array.isArray(item.secret_fields) ? item.secret_fields : []
    }));
}

function badgeForStatus(status) {
  if (status?.connected) return { label: "Подключено", className: "badge good" };
  if (status?.error) return { label: "Ошибка", className: "badge bad" };
  return { label: "Не подключено", className: "badge neutral" };
}

export function App() {
  const [apiBase, setApiBase] = useState(DEFAULT_API);
  const [form, setForm] = useState({ email: "", business_name: "", website: "", intent: DEFAULT_INTENT });
  const [ctaLoading, setCtaLoading] = useState(false);
  const [ctaError, setCtaError] = useState("");
  const [ctaResult, setCtaResult] = useState(null);
  const [intakeId, setIntakeId] = useState(initialIntakeId());
  const [providers, setProviders] = useState(FALLBACK_PROVIDERS);
  const [providerStatuses, setProviderStatuses] = useState({});
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [providerSecrets, setProviderSecrets] = useState({});
  const [providerExternalRef, setProviderExternalRef] = useState("");
  const [connectLoading, setConnectLoading] = useState(false);
  const [connectError, setConnectError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [technicalOpen, setTechnicalOpen] = useState(false);

  const endpoints = useMemo(() => {
    const base = apiBase.replace(/\/$/, "");
    return {
      health: `${base}/health`,
      readyz: `${base}/readyz`,
      openapi: `${base}/openapi.json`,
      ctaStart: `${base}/public-site/cta/start`,
      ctaStatus: (id) => `${base}/public-site/cta/${encodeURIComponent(id)}`,
      providerCatalog: `${base}/control-plane/provider-admin/catalog`,
      providerActivate: `${base}/control-plane/provider-admin/activate`
    };
  }, [apiBase]);

  useEffect(() => {
    const id = initialIntakeId();
    if (!id) return;
    let cancelled = false;
    getJson(endpoints.ctaStatus(id))
      .then((data) => {
        if (!cancelled && data?.found !== false) {
          setCtaResult(data);
          setIntakeId(id);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [endpoints]);

  useEffect(() => {
    if (!ctaResult?.tenant_id || !ctaResult?.business_id) return;
    let cancelled = false;
    setCatalogLoading(true);
    const url = new URL(endpoints.providerCatalog);
    url.searchParams.set("tenant_id", ctaResult.tenant_id);
    url.searchParams.set("business_id", ctaResult.business_id);
    getJson(url.toString())
      .then((data) => {
        if (!cancelled) {
          setProviders(normalizeProviderCatalog(data));
          const statuses = data?.activation_statuses || data?.statuses || [];
          if (Array.isArray(statuses)) {
            setProviderStatuses(Object.fromEntries(statuses.map((item) => [item.provider_key, item])));
          }
        }
      })
      .catch(() => {
        if (!cancelled) setProviders(FALLBACK_PROVIDERS);
      })
      .finally(() => { if (!cancelled) setCatalogLoading(false); });
    return () => { cancelled = true; };
  }, [ctaResult, endpoints]);

  const submitCta = async (event) => {
    event.preventDefault();
    setCtaLoading(true);
    setCtaError("");
    try {
      const result = await postJson(endpoints.ctaStart, {
        email: form.email.trim(),
        business_name: form.business_name.trim(),
        website: form.website.trim(),
        source: "businessaios_product_onboarding",
        intent: form.intent,
        requested_surface: "self_service_business_workspace"
      });
      setCtaResult(result);
      setIntakeId(result.intake_id || "");
      if (result?.intake_id) window.history.replaceState(null, "", `?intake_id=${encodeURIComponent(result.intake_id)}`);
      setActiveTab("integrations");
    } catch (e) {
      setCtaError(String(e?.message || e));
    } finally {
      setCtaLoading(false);
    }
  };

  const openProvider = (provider) => {
    setSelectedProvider(provider);
    setProviderSecrets({});
    setProviderExternalRef(form.website || "");
    setConnectError("");
  };

  const connectProvider = async (event) => {
    event.preventDefault();
    if (!selectedProvider || !ctaResult) return;
    setConnectLoading(true);
    setConnectError("");
    try {
      const status = await postJson(endpoints.providerActivate, {
        tenant_id: ctaResult.tenant_id,
        business_id: ctaResult.business_id,
        provider_key: selectedProvider.provider_key,
        ownership_key: `owner:${ctaResult.business_id}`,
        requested_by: ctaResult.user_id || form.email || "self_service_owner",
        external_ref: providerExternalRef.trim() || form.website || selectedProvider.provider_key,
        metadata: {
          source: "self_service_workspace",
          probe_mode: "dry_run",
          verified_owner: true,
          autonomy_tier: "supervised"
        },
        secrets: providerSecrets
      });
      setProviderStatuses((prev) => ({ ...prev, [selectedProvider.provider_key]: status }));
      setSelectedProvider(null);
    } catch (e) {
      setConnectError(String(e?.message || e));
    } finally {
      setConnectLoading(false);
    }
  };

  const connectedCount = Object.values(providerStatuses).filter((item) => item?.connected).length;
  const businessName = form.business_name || ctaResult?.business_id?.replace(/^business-/, "") || "Ваш бизнес";

  if (!ctaResult) {
    return (
      <main className="onboarding-shell">
        <section className="onboarding-copy">
          <div className="brand-mark">BA</div>
          <p className="eyebrow">BusinessAIOS</p>
          <h1>Подключите бизнес.<br />Остальное соберём вокруг него.</h1>
          <p className="lead">Система начинает в безопасном режиме: собирает данные, показывает возможности и ничего не публикует и не тратит без разрешения.</p>
          <div className="promise-list">
            <span>✓ Подключение источников в одном месте</span>
            <span>✓ Сначала анализ, затем действия</span>
            <span>✓ Внешние записи только с контролем и доказательствами</span>
          </div>
        </section>
        <section className="onboarding-card">
          <div className="step-pill">Шаг 1 из 3 · Ваш бизнес</div>
          <h2>Начнём с основы</h2>
          <p className="muted">Этого достаточно, чтобы создать рабочее пространство. Интеграции подключим следующим шагом.</p>
          <form className="product-form" onSubmit={submitCta}>
            <label>Название бизнеса<input value={form.business_name} onChange={(e) => setForm({ ...form, business_name: e.target.value })} placeholder="Например, Северная кофейня" required /></label>
            <label>Рабочий email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="owner@company.ru" required /></label>
            <label>Сайт или основной канал<input value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="https://company.ru или @telegram" /></label>
            <label>Что нужно в первую очередь?
              <select value={form.intent} onChange={(e) => setForm({ ...form, intent: e.target.value })}>
                <option value="pilot">Увидеть возможности и точки роста</option>
                <option value="connectors">Собрать данные из сервисов</option>
                <option value="autopilot">Подготовить безопасную автоматизацию</option>
              </select>
            </label>
            <button className="primary large" type="submit" disabled={ctaLoading}>{ctaLoading ? "Создаём пространство…" : "Создать рабочее пространство"}</button>
          </form>
          {ctaError ? <div className="inline-error">Не удалось создать пространство: {ctaError}</div> : null}
          <p className="privacy-note">На старте включён режим «Советник»: никаких автоматических списаний, рассылок или публикаций.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark small">BA</div><div><strong>BusinessAIOS</strong><span>{businessName}</span></div></div>
        <nav>
          <button className={activeTab === "overview" ? "nav-item active" : "nav-item"} onClick={() => setActiveTab("overview")}>Обзор</button>
          <button className={activeTab === "integrations" ? "nav-item active" : "nav-item"} onClick={() => setActiveTab("integrations")}>Подключения <em>{connectedCount}</em></button>
          <button className={activeTab === "automation" ? "nav-item active" : "nav-item"} onClick={() => setActiveTab("automation")}>Автоматизация</button>
        </nav>
        <div className="sidebar-foot"><span className="status-dot" /> Режим: Советник</div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div><p className="eyebrow">Рабочее пространство</p><h1>{businessName}</h1></div><div className="safe-chip">Безопасный режим</div></header>

        {activeTab === "overview" ? (
          <>
            <section className="welcome-panel"><div><p className="eyebrow">Следующий лучший шаг</p><h2>{connectedCount ? "Данные подключены — можно строить картину бизнеса" : "Подключите первый источник данных"}</h2><p>{connectedCount ? "BusinessAIOS будет собирать факты и показывать возможности без самостоятельных внешних действий." : "CRM, магазин, сайт или мессенджер — достаточно одного источника, чтобы начать получать полезную картину."}</p></div><button className="primary" onClick={() => setActiveTab("integrations")}>{connectedCount ? "Управлять подключениями" : "Выбрать источник"}</button></section>
            <section className="metric-grid">
              <article className="metric-card"><span>Подключено источников</span><strong>{connectedCount}</strong><small>{connectedCount ? "готовы к безопасному чтению" : "начните с одного"}</small></article>
              <article className="metric-card"><span>Найдено возможностей</span><strong>—</strong><small>появятся после первого импорта</small></article>
              <article className="metric-card"><span>Действий без подтверждения</span><strong>0</strong><small>контроль владельца сохранён</small></article>
            </section>
            <section className="section-card"><div className="section-heading"><div><p className="eyebrow">Первый результат</p><h2>Здесь будут не графики ради графиков</h2></div></div><div className="empty-insight"><div className="insight-icon">↗</div><div><strong>После синхронизации система покажет конкретные возможности</strong><p>Например: незавершённые обращения, потерянные клиенты, неэффективные расходы или операции, которые можно автоматизировать.</p></div></div></section>
          </>
        ) : null}

        {activeTab === "integrations" ? (
          <section>
            <div className="section-heading"><div><p className="eyebrow">Шаг 2 из 3</p><h2>Подключите сервисы, которыми уже пользуетесь</h2><p className="muted">Сначала подключение и проверка. Внешние записи остаются заблокированы до явного разрешения.</p></div><span className="count-chip">{catalogLoading ? "Загружаем…" : `${providers.length} доступно`}</span></div>
            <div className="provider-grid">
              {providers.map((provider) => {
                const status = providerStatuses[provider.provider_key];
                const badge = badgeForStatus(status);
                return <article className="provider-card" key={provider.provider_key}>
                  <div className="provider-icon">{(provider.title || "?").slice(0, 2).toUpperCase()}</div>
                  <div className="provider-body"><div className="provider-title"><h3>{provider.title}</h3><span className={badge.className}>{badge.label}</span></div><p>{provider.description}</p><small>{DOMAIN_LABELS[provider.domain] || provider.domain}</small></div>
                  <button className={status?.connected ? "secondary" : "primary"} onClick={() => openProvider(provider)}>{status?.connected ? "Настроить" : "Подключить"}</button>
                </article>;
              })}
            </div>
          </section>
        ) : null}

        {activeTab === "automation" ? (
          <section>
            <div className="section-heading"><div><p className="eyebrow">Шаг 3 из 3</p><h2>Как BusinessAIOS может действовать</h2><p className="muted">Уровень автономии повышается только после подключения данных и проверки контуров.</p></div></div>
            <div className="mode-grid">
              <article className="mode-card selected"><div className="mode-radio">●</div><h3>Советник</h3><p>Анализирует бизнес и предлагает действия. Ничего не отправляет и не публикует самостоятельно.</p><span className="badge good">Включено</span></article>
              <article className="mode-card"><div className="mode-radio">○</div><h3>Помощник</h3><p>Безопасные операции автоматизируются, важные действия ждут подтверждения владельца.</p><span className="badge neutral">После проверки</span></article>
              <article className="mode-card"><div className="mode-radio">○</div><h3>Автопилот</h3><p>Работает в заданных лимитах, с бюджетными, риск- и evidence-ограничениями.</p><span className="badge neutral">Недоступно до готовности</span></article>
            </div>
          </section>
        ) : null}

        <details className="technical" open={technicalOpen} onToggle={(e) => setTechnicalOpen(e.currentTarget.open)}><summary>Техническая информация</summary><div className="technical-grid"><label>API<input value={apiBase} onChange={(e) => setApiBase(e.target.value)} /></label><div><span>Workspace ID</span><code>{intakeId}</code></div><div><span>Tenant</span><code>{ctaResult.tenant_id}</code></div><a href={endpoints.openapi} target="_blank" rel="noreferrer">OpenAPI</a></div></details>
      </section>

      {selectedProvider ? <div className="modal-backdrop" onMouseDown={() => !connectLoading && setSelectedProvider(null)}><section className="modal" onMouseDown={(e) => e.stopPropagation()}><div className="modal-head"><div><p className="eyebrow">Подключение</p><h2>{selectedProvider.title}</h2></div><button className="icon-button" onClick={() => setSelectedProvider(null)}>×</button></div><p className="muted">Ключи сохраняются через существующий secret-vault. Сразу после подключения выполняется безопасная проверка без внешних write-действий.</p><form className="product-form" onSubmit={connectProvider}><label>Адрес / идентификатор аккаунта<input value={providerExternalRef} onChange={(e) => setProviderExternalRef(e.target.value)} placeholder={form.website || "URL, workspace или account ID"} required /></label>{(selectedProvider.secret_fields || []).map((field) => <label key={field.field_key || field.secret_name}>{field.label || field.field_key}<input type={String(field.secret_kind || "").includes("password") || String(field.field_key || "").includes("token") || String(field.field_key || "").includes("secret") || String(field.field_key || "").includes("key") ? "password" : "text"} value={providerSecrets[field.field_key] || ""} onChange={(e) => setProviderSecrets((prev) => ({ ...prev, [field.field_key]: e.target.value }))} placeholder={field.placeholder || ""} required={field.required !== false} /></label>)}{connectError ? <div className="inline-error">{connectError}</div> : null}<div className="modal-actions"><button type="button" className="secondary" onClick={() => setSelectedProvider(null)}>Отмена</button><button className="primary" type="submit" disabled={connectLoading}>{connectLoading ? "Проверяем…" : "Подключить и проверить"}</button></div></form></section></div> : null}
    </main>
  );
}

export { getJson, postJson, normalizeProviderCatalog };
