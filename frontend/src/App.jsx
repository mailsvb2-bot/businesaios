import { useEffect, useMemo, useState } from "react";

const DEFAULT_API = "https://api.businessaios.ru";

const GOALS = [
  { value: "growth", title: "Больше клиентов", text: "Найти потери в воронке и точки роста продаж." },
  { value: "retention", title: "Возвращать клиентов", text: "Находить клиентов, которых стоит реактивировать." },
  { value: "ads_efficiency", title: "Эффективнее реклама", text: "Искать неэффективный расход и проблемы атрибуции." },
  { value: "sales", title: "Сильнее продажи", text: "Показывать зависшие сделки и пропущенные follow-up." },
  { value: "operations", title: "Меньше рутины", text: "Находить повторяющиеся операции и задержки исполнения." }
];

const AUTONOMY = [
  {
    value: "advisor",
    title: "Советник",
    badge: "Самый безопасный старт",
    text: "Анализирует бизнес и предлагает действия. Ничего сам не отправляет и не тратит."
  },
  {
    value: "assistant",
    title: "Помощник",
    badge: "Рекомендуем после знакомства",
    text: "Автоматизирует безопасные шаги, а важные действия отправляет вам на подтверждение."
  },
  {
    value: "autopilot",
    title: "Автопилот",
    badge: "После проверки интеграций",
    text: "Целевой режим автономной работы в заданных лимитах. Включается только после проверок безопасности."
  }
];

const STEP_LABELS = ["О бизнесе", "Цель", "Интеграции", "Режим"];

async function getJson(url) {
  const resp = await fetch(url);
  const text = await resp.text();
  let parsed;
  try {
    parsed = text ? JSON.parse(text) : {};
  } catch {
    parsed = { raw: text };
  }
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
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
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return parsed;
}

function initialIntakeId() {
  try {
    return new URLSearchParams(window.location.search).get("intake_id") || "";
  } catch {
    return "";
  }
}

function providerInitial(title) {
  return String(title || "?").trim().slice(0, 2).toUpperCase();
}

function statusClass(item) {
  if (item.availability === "available_read_only") return "ready";
  if (item.availability === "preparing") return "preparing";
  return "roadmap";
}

function Workspace({ data, apiBase, onRestart }) {
  const profile = data.business_profile || {};
  const progress = data.onboarding_progress || {};
  const firstValue = data.first_value_preview || {};
  const integrations = data.integration_plan || [];
  const secureConnectUrl = `${apiBase.replace(/\/$/, "")}/web/provider-tokens`;

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand-mark">B</span>
          <span>BusinessAIOS</span>
        </a>
        <div className="topbar-actions">
          <span className="safe-chip">Read-only onboarding</span>
          <button className="ghost small" onClick={onRestart}>Новый бизнес</button>
        </div>
      </header>

      <section className="workspace-hero">
        <div>
          <p className="eyebrow">Кабинет бизнеса</p>
          <h1>{profile.name || "Ваш бизнес"}</h1>
          <p className="lead">
            База создана. Теперь подключите реальные источники данных — после первого sync BusinessAIOS покажет конкретные точки потерь и роста.
          </p>
        </div>
        <div className="progress-card">
          <div className="progress-head">
            <span>Настройка</span>
            <strong>{progress.percent ?? 0}%</strong>
          </div>
          <div className="progress-track"><span style={{ width: `${progress.percent ?? 0}%` }} /></div>
          <small>Следующий шаг: безопасно подтвердить доступ к выбранным источникам.</small>
        </div>
      </section>

      <section className="summary-grid">
        <article className="summary-card">
          <span className="summary-icon">◎</span>
          <div><small>Цель</small><strong>{GOALS.find((goal) => goal.value === profile.goal)?.title || profile.goal || "Рост"}</strong></div>
        </article>
        <article className="summary-card">
          <span className="summary-icon">⌁</span>
          <div><small>Источники</small><strong>{integrations.length} выбрано</strong></div>
        </article>
        <article className="summary-card">
          <span className="summary-icon">◇</span>
          <div><small>Режим</small><strong>{data.user_functionality?.autonomy_mode_label || "Советник"}</strong></div>
        </article>
      </section>

      <section className="workspace-grid">
        <article className="panel primary-panel">
          <div className="panel-title-row">
            <div>
              <p className="eyebrow">Следующий шаг</p>
              <h2>Подключите данные</h2>
            </div>
            <span className="privacy-badge">Запись выключена</span>
          </div>
          <p className="muted-text">
            Сначала BusinessAIOS только читает данные. Отправка сообщений, публикации и рекламные расходы остаются заблокированными.
          </p>
          <div className="connection-list">
            {integrations.length ? integrations.map((item) => (
              <div className="connection-row" key={item.provider_key}>
                <div className="provider-logo">{providerInitial(item.title)}</div>
                <div className="connection-copy">
                  <strong>{item.title}</strong>
                  <span>{item.status === "credentials_required" ? "Нужно подтвердить доступ" : "Пока недоступно"}</span>
                </div>
                <span className={`dot ${item.status === "credentials_required" ? "orange" : "gray"}`} />
              </div>
            )) : <p className="empty-state">Источники ещё не выбраны.</p>}
          </div>
          <a className="button primary wide-button" href={secureConnectUrl}>
            Перейти к защищённому подключению
          </a>
          <small className="helper-text">Ключи и токены вводятся только в защищённом control-plane и не хранятся в браузере.</small>
        </article>

        <article className="panel value-panel">
          <p className="eyebrow">Что получите первым</p>
          <h2>{firstValue.title || "Первый полезный результат"}</h2>
          <p className="muted-text">{firstValue.message}</p>
          <div className="check-list">
            {(firstValue.checks || []).map((item) => (
              <div className="check-row" key={item}><span>✓</span><strong>{item}</strong></div>
            ))}
          </div>
          <div className="truth-note">
            Здесь нет придуманных цифр. Финансовые выводы появятся только после реального sync ваших данных.
          </div>
        </article>
      </section>

      <section className="panel business-card">
        <div>
          <p className="eyebrow">Профиль</p>
          <h2>{profile.name || "Бизнес"}</h2>
        </div>
        <div className="business-meta">
          {profile.industry ? <span>{profile.industry}</span> : null}
          {profile.city ? <span>{profile.city}</span> : null}
          {profile.website ? <a href={profile.website} target="_blank" rel="noreferrer">{profile.website}</a> : null}
        </div>
      </section>

      <details className="diagnostics">
        <summary>Техническая информация</summary>
        <pre>{JSON.stringify({ intake_id: data.intake_id, tenant_id: data.tenant_id, business_id: data.business_id, status: data.onboarding_status }, null, 2)}</pre>
      </details>
    </main>
  );
}

export function App() {
  const [apiBase] = useState(DEFAULT_API);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [marketLoading, setMarketLoading] = useState(true);
  const [error, setError] = useState("");
  const [marketplace, setMarketplace] = useState([]);
  const [selectedProviders, setSelectedProviders] = useState([]);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState({
    email: "",
    business_name: "",
    website: "",
    industry: "",
    city: "",
    business_model: "services",
    goal: "growth",
    autonomy_mode: "advisor"
  });

  const endpoints = useMemo(() => {
    const base = apiBase.replace(/\/$/, "");
    return {
      integrations: `${base}/public-site/integrations`,
      ctaStart: `${base}/public-site/cta/start`,
      ctaStatus: (id) => `${base}/public-site/cta/${encodeURIComponent(id)}`
    };
  }, [apiBase]);

  useEffect(() => {
    let cancelled = false;
    setMarketLoading(true);
    getJson(endpoints.integrations)
      .then((payload) => {
        if (!cancelled) setMarketplace(Array.isArray(payload.items) ? payload.items : []);
      })
      .catch(() => {
        if (!cancelled) setError("Не удалось загрузить каталог интеграций. Проверьте API и повторите попытку.");
      })
      .finally(() => {
        if (!cancelled) setMarketLoading(false);
      });
    return () => { cancelled = true; };
  }, [endpoints]);

  useEffect(() => {
    const intakeId = initialIntakeId();
    if (!intakeId) return;
    let cancelled = false;
    setLoading(true);
    getJson(endpoints.ctaStatus(intakeId))
      .then((payload) => {
        if (!cancelled && payload.ok) setResult(payload);
      })
      .catch(() => {
        if (!cancelled) setError("Не удалось открыть сохранённый кабинет бизнеса.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [endpoints]);

  const updateForm = (key) => (event) => {
    setForm((prev) => ({ ...prev, [key]: event.target.value }));
  };

  const toggleProvider = (item) => {
    if (!item.selectable) return;
    setSelectedProviders((prev) => (
      prev.includes(item.provider_key)
        ? prev.filter((key) => key !== item.provider_key)
        : [...prev, item.provider_key]
    ));
  };

  const canContinue = () => {
    if (step === 0) return Boolean(form.business_name.trim() && form.email.trim());
    if (step === 1) return Boolean(form.goal);
    if (step === 2) return selectedProviders.length > 0;
    return Boolean(form.autonomy_mode);
  };

  const finishOnboarding = async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await postJson(endpoints.ctaStart, {
        ...form,
        selected_providers: selectedProviders,
        intent: form.goal,
        source: "businessaios_product_onboarding",
        requested_surface: "business_workspace"
      });
      setResult(payload);
      if (payload.intake_id) {
        window.history.replaceState(null, "", `?intake_id=${encodeURIComponent(payload.intake_id)}`);
      }
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
    setError("");
  };

  if (result) return <Workspace data={result} apiBase={apiBase} onRestart={restart} />;

  return (
    <main className="onboarding-shell">
      <header className="topbar onboarding-topbar">
        <div className="brand"><span className="brand-mark">B</span><span>BusinessAIOS</span></div>
        <span className="topbar-note">Настройка бизнеса</span>
      </header>

      <section className="onboarding-layout">
        <aside className="intro-column">
          <p className="eyebrow">Business Autopilot</p>
          <h1>Подключите бизнес.<br />Остальное система разберёт сама.</h1>
          <p className="lead">
            Сначала только чтение и анализ. Никаких расходов, сообщений клиентам или публикаций без вашего разрешения.
          </p>
          <div className="trust-list">
            <div><span>✓</span><p><strong>Безопасный старт</strong><small>Внешние write-действия выключены.</small></p></div>
            <div><span>✓</span><p><strong>Честные статусы</strong><small>Показываем только реально доступные интеграции.</small></p></div>
            <div><span>✓</span><p><strong>Первый результат на ваших данных</strong><small>Без выдуманных финансовых обещаний.</small></p></div>
          </div>
        </aside>

        <section className="onboarding-card">
          <div className="stepper">
            {STEP_LABELS.map((label, index) => (
              <div className={`step ${index === step ? "active" : ""} ${index < step ? "done" : ""}`} key={label}>
                <span>{index < step ? "✓" : index + 1}</span><small>{label}</small>
              </div>
            ))}
          </div>

          {step === 0 ? (
            <div className="step-content">
              <div className="section-heading"><p className="eyebrow">Шаг 1</p><h2>Расскажите о бизнесе</h2><p>Этого достаточно, чтобы создать отдельный защищённый workspace.</p></div>
              <div className="form-grid">
                <label className="full">Название бизнеса<input value={form.business_name} onChange={updateForm("business_name")} placeholder="Например, Студия Линия" autoFocus /></label>
                <label>Email владельца<input value={form.email} onChange={updateForm("email")} placeholder="you@company.ru" type="email" /></label>
                <label>Сайт или страница<input value={form.website} onChange={updateForm("website")} placeholder="https://..." /></label>
                <label>Сфера<input value={form.industry} onChange={updateForm("industry")} placeholder="Услуги, магазин, образование..." /></label>
                <label>Город<input value={form.city} onChange={updateForm("city")} placeholder="Москва" /></label>
                <label className="full">Модель бизнеса<select value={form.business_model} onChange={updateForm("business_model")}><option value="services">Услуги</option><option value="commerce">Товары / e-commerce</option><option value="marketplace">Маркетплейсы</option><option value="b2b">B2B</option><option value="mixed">Смешанная</option></select></label>
              </div>
            </div>
          ) : null}

          {step === 1 ? (
            <div className="step-content">
              <div className="section-heading"><p className="eyebrow">Шаг 2</p><h2>Что важнее прямо сейчас?</h2><p>BusinessAIOS начнёт анализ с выбранной бизнес-задачи.</p></div>
              <div className="choice-grid">
                {GOALS.map((goal) => (
                  <button type="button" className={`choice-card ${form.goal === goal.value ? "selected" : ""}`} onClick={() => setForm((prev) => ({ ...prev, goal: goal.value }))} key={goal.value}>
                    <span className="radio-dot" /><strong>{goal.title}</strong><small>{goal.text}</small>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {step === 2 ? (
            <div className="step-content integrations-step">
              <div className="section-heading"><p className="eyebrow">Шаг 3</p><h2>Где уже живут данные бизнеса?</h2><p>Выберите хотя бы один источник. Подключение начнётся в read-only режиме.</p></div>
              {marketLoading ? <div className="loading-box">Загружаем доступные интеграции…</div> : null}
              <div className="integration-grid">
                {marketplace.map((item) => {
                  const selected = selectedProviders.includes(item.provider_key);
                  return (
                    <button type="button" disabled={!item.selectable} className={`integration-card ${selected ? "selected" : ""} ${!item.selectable ? "disabled" : ""}`} onClick={() => toggleProvider(item)} key={item.provider_key}>
                      <div className="integration-card-head"><span className="provider-logo">{providerInitial(item.title)}</span>{item.recommended ? <span className="recommended">Рекомендуем</span> : null}</div>
                      <strong>{item.title}</strong>
                      <small>{item.description}</small>
                      <span className={`status-pill ${statusClass(item)}`}>{selected ? "Выбрано ✓" : item.availability_label}</span>
                    </button>
                  );
                })}
              </div>
              <p className="selection-count">Выбрано: <strong>{selectedProviders.length}</strong></p>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="step-content">
              <div className="section-heading"><p className="eyebrow">Шаг 4</p><h2>Сколько свободы дать системе?</h2><p>На старте любое внешнее write-действие всё равно остаётся заблокированным до проверки.</p></div>
              <div className="autonomy-grid">
                {AUTONOMY.map((mode) => (
                  <button type="button" className={`autonomy-card ${form.autonomy_mode === mode.value ? "selected" : ""}`} onClick={() => setForm((prev) => ({ ...prev, autonomy_mode: mode.value }))} key={mode.value}>
                    <span className="mode-badge">{mode.badge}</span><strong>{mode.title}</strong><small>{mode.text}</small>
                  </button>
                ))}
              </div>
              <div className="launch-preview"><span>✓</span><div><strong>После создания кабинета</strong><p>Вы увидите выбранные источники, безопасный путь их авторизации и первый анализ, который появится после реального sync.</p></div></div>
            </div>
          ) : null}

          {error ? <div className="error-box">{error}</div> : null}

          <div className="navigation-row">
            <button type="button" className="ghost" disabled={step === 0 || loading} onClick={() => setStep((value) => Math.max(0, value - 1))}>Назад</button>
            {step < STEP_LABELS.length - 1 ? (
              <button type="button" className="primary" disabled={!canContinue() || loading} onClick={() => setStep((value) => Math.min(STEP_LABELS.length - 1, value + 1))}>Продолжить →</button>
            ) : (
              <button type="button" className="primary launch" disabled={!canContinue() || loading} onClick={finishOnboarding}>{loading ? "Создаём кабинет…" : "Создать мой BusinessAIOS →"}</button>
            )}
          </div>
        </section>
      </section>

      <footer className="product-footer">BusinessAIOS · безопасная автоматизация бизнеса · write-действия только после проверки</footer>
    </main>
  );
}

export { getJson, postJson };
