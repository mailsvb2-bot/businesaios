import { useState } from "react";
import {
  ACQUISITION_ADVANCED_FIELDS,
  ACQUISITION_DEFAULTS,
  ACQUISITION_FIELDS,
  ACQUISITION_PRIMARY_FIELDS,
  acquisitionPayload,
  formatMetric as fmt,
  isAcquisitionFormValid
} from "./acquisitionPlannerModel.js";
import "./AcquisitionPlanner.css";

const PUBLIC_BRAND = import.meta.env.VITE_BAI_PUBLIC_BRAND_CLIENTPLATFORM === "true" ? "ClientPlatform" : "BusinessAIOS";
function renderFields(fields, form, update, disabled, valid) {
  return fields.map(([key, label, hint, min, max, step]) => (
    <label key={key}>
      {label}
      <input type="number" min={min} max={max} step={step} value={form[key]} onChange={update(key)} disabled={disabled} aria-invalid={!valid} />
      <small>{hint}</small>
    </label>
  ));
}

const PROMOTION_LAUNCH_ENABLED = String(import.meta.env.VITE_BAI_PROMOTION_LAUNCH || "").toLowerCase() === "true";
const LAUNCH_CHECKS = {
  plan_feasible: "Цель достижима", economics_sustainable: "Экономика устойчива",
  budget_cap_positive: "Недельный лимит положительный", provider_known: "Рекламный кабинет известен",
  provider_write_capability: "Можно создавать кампании", provider_verification_capability: "Можно проверить результат",
  provider_production_ready: "Боевой доступ проверен"
};

export function AcquisitionPlanner({ enabled, onEvaluate, onLaunch }) {
  const [launch, setLaunch] = useState(null);
  const [lastPayload, setLastPayload] = useState(null);
  const [form, setForm] = useState(ACQUISITION_DEFAULTS);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const validationFields = showAdvanced ? ACQUISITION_FIELDS : ACQUISITION_PRIMARY_FIELDS;
  const valid = isAcquisitionFormValid(form, validationFields);
  const update = (key) => (event) => {
    setForm((previous) => ({ ...previous, [key]: event.target.value }));
    setResult(null);
    setLaunch(null);
    setLastPayload(null);
    setError("");
  };

  const evaluate = async () => {
    if (!valid) {
      setResult(null);
      setError("Проверьте значения: все поля должны быть заполнены и попадать в допустимый диапазон.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const effectiveForm = showAdvanced ? form : {
        ...ACQUISITION_DEFAULTS,
        target_customers: form.target_customers,
        total_budget: form.total_budget,
        target_days: form.target_days,
        daily_budget: Number(form.target_days) > 0 ? Number(form.total_budget) / Number(form.target_days) : 0
      };
      const payload = acquisitionPayload(effectiveForm);
      setLastPayload(payload);
      setLaunch(null);
      setResult(await onEvaluate(payload));
    } catch {
      setError("Не удалось посчитать сценарий. Проверьте соединение и повторите попытку.");
    } finally {
      setBusy(false);
    }
  };

  const dryRunLaunch = async () => {
    if (!PROMOTION_LAUNCH_ENABLED || !onLaunch || !lastPayload || busy) return;
    setBusy(true); setError("");
    try {
      const preview = await onLaunch({ plan_input: lastPayload, mode: "dry_run", provider: "yandex_direct" });
      if (preview.mode !== "dry_run" || preview.spend_authorized !== false || !Array.isArray(preview.checks)) {
        throw new Error("unsafe");
      }
      setLaunch(preview);
    } catch {
      setError("Не удалось проверить запуск продвижения.");
    } finally {
      setBusy(false);
    }
  };

  const plan = result?.plan || null;
  const economics = result?.economics || null;
  return (
    <section className="planner-shell" aria-labelledby="acquisition-planner-title">
      <article className="panel planner-panel">
        <div className="planner-heading">
          <div>
            <p className="eyebrow">Быстрый расчёт</p>
            <h2 id="acquisition-planner-title">Сколько клиентов можно получить с вашим бюджетом?</h2>
            <p className="muted-text">Укажите цель, бюджет и срок. Остальные параметры можно уточнить при желании.</p>
          </div>
          <span className="privacy-badge">Только расчёт</span>
        </div>
        {!enabled ? <div className="planner-session-note">Расчёт временно недоступен, пока защищённый вход в кабинет не восстановлен. Используйте «Повторить защищённый вход» в блоке подключений выше.</div> : null}
        {error ? <div className="planner-error" role="alert">{error}</div> : null}
        <div className="planner-form planner-primary-form">{renderFields(ACQUISITION_PRIMARY_FIELDS, form, update, !enabled || busy, valid)}</div>
        <button type="button" className="ghost planner-advanced-toggle" onClick={() => setShowAdvanced((value) => !value)} disabled={!enabled || busy} aria-expanded={showAdvanced}>
          {showAdvanced ? "Скрыть дополнительные параметры" : "Уточнить расчёт вручную"}
        </button>
        {showAdvanced ? (
          <div className="planner-advanced-block">
            <p>Эти параметры необязательны для быстрого сценария. После подключения реальных данных {PUBLIC_BRAND} сможет опираться на фактические показатели бизнеса.</p>
            <div className="planner-form planner-advanced-form">{renderFields(ACQUISITION_ADVANCED_FIELDS, form, update, !enabled || busy, valid)}</div>
          </div>
        ) : null}
        <div className="planner-actions">
          <p>Это модель «что будет, если». После подключения реальных данных её можно сравнить с фактическими показателями бизнеса.</p>
          <button type="button" className="primary" onClick={evaluate} disabled={!enabled || busy || !valid}>{busy ? "Считаем…" : "Рассчитать"}</button>
        </div>
        {plan ? <div className={`planner-result ${plan.feasible ? "feasible" : "constrained"}`}>
          <div className="planner-result-copy"><p className="eyebrow">{plan.feasible ? "Цель достижима" : "Есть ограничение"}</p><h3>{plan.headline}</h3><p>{plan.narrative}</p></div>
          <div className="planner-metrics"><div><small>Достижимо клиентов</small><strong>{fmt(plan.achievable_customers, 0)}</strong></div><div><small>Нужный бюджет</small><strong>{fmt(plan.required_budget)}</strong></div><div><small>Бюджет в день</small><strong>{fmt(plan.recommended_daily_budget)}</strong></div><div><small>Оценочный срок</small><strong>{plan.estimated_days === null ? "—" : `${fmt(plan.estimated_days, 1)} дн.`}</strong></div><div><small>Дефицит клиентов</small><strong>{fmt(plan.customer_gap, 0)}</strong></div><div><small>Дефицит бюджета</small><strong>{fmt(plan.budget_gap)}</strong></div></div>
          {economics ? <div className="planner-economics"><span>Стоимость клиента <strong>{fmt(economics.blended_cac)}</strong></span><span>Ценность / стоимость <strong>{fmt(economics.ltv_to_cac_ratio, 2)}</strong></span><span>Окупаемость <strong>{fmt(economics.payback_months, 1)} мес.</strong></span><span>Экономика <strong>{economics.sustainable ? "устойчивая" : "требует правки"}</strong></span></div> : null}
          {Array.isArray(plan.recommendations) && plan.recommendations.length ? <div className="planner-recommendations"><h4>Что изменить</h4>{plan.recommendations.slice(0, 3).map((item) => <div key={`${item.kind}-${item.priority}`}><strong>{item.title}</strong><p>{item.description}</p></div>)}</div> : null}
          {PROMOTION_LAUNCH_ENABLED ? <div className="planner-launch">
            <button type="button" className="primary" onClick={dryRunLaunch} disabled={!enabled || busy || !onLaunch}>Проверить запуск продвижения</button>
            {launch ? <div role="status">
              <p>Пробная проверка без расходов. Недельный предел: {fmt(launch.weekly_cap_minor / 100)} ₽.</p>
              <ul>{launch.checks.map((item) => <li key={item.check}>{item.passed ? "✓" : "✗"} {LAUNCH_CHECKS[item.check] || item.check}</li>)}</ul>
              <p>{launch.apply_possible ? "Технические проверки пройдены. Для реального запуска требуется отдельное согласование владельца."
                : "Запуск пока невозможен: устраните отмеченные ограничения."}</p>
            </div> : null}
          </div> : null}
          <p className="planner-disclaimer">Источник цифр в этом блоке — введённые вами предположения. Это не подтверждённые показатели бизнеса и не обещание результата.</p>
        </div> : null}
      </article>
    </section>
  );
}
