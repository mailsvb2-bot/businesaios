import { useState } from "react";
import { ACQUISITION_DEFAULTS, ACQUISITION_FIELDS, acquisitionPayload, formatMetric as fmt } from "./acquisitionPlannerModel.js";
import "./AcquisitionPlanner.css";

export function AcquisitionPlanner({ enabled, onEvaluate }) {
  const [form, setForm] = useState(ACQUISITION_DEFAULTS);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const update = (key) => (event) => {
    setForm((previous) => ({ ...previous, [key]: event.target.value }));
    setResult(null);
    setError("");
  };

  const evaluate = async () => {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await onEvaluate(acquisitionPayload(form)));
    } catch (err) {
      setError(`Не удалось посчитать сценарий: ${err.message || "ошибка API"}`);
    } finally {
      setBusy(false);
    }
  };

  const plan = result?.plan || null;
  const economics = result?.economics || null;
  return (
    <section className="planner-shell" aria-labelledby="acquisition-planner-title">
      <article className="panel planner-panel">
        <div className="planner-heading"><div><p className="eyebrow">Сценарий по вашим предположениям</p><h2 id="acquisition-planner-title">Сколько клиентов реально взять с этим бюджетом?</h2><p className="muted-text">Расчёт использует основную модель воронки, бюджета, срока и CAC/LTV. Он ничего не запускает и не меняет во внешних системах.</p></div><span className="privacy-badge">Только расчёт</span></div>
        {!enabled ? <div className="planner-session-note">Для расчёта нужна активная OWNER-сессия. Она намеренно не сохраняется после перезагрузки страницы.</div> : null}
        {error ? <div className="planner-error">{error}</div> : null}
        <div className="planner-form">{ACQUISITION_FIELDS.map(([key, label, hint, min, max, step]) => <label key={key}>{label}<input type="number" min={min} max={max} step={step} value={form[key]} onChange={update(key)} disabled={!enabled || busy} /><small>{hint}</small></label>)}</div>
        <div className="planner-actions"><p>Это модель «что будет, если». После real sync её можно сравнить с фактическими данными бизнеса.</p><button type="button" className="primary" onClick={evaluate} disabled={!enabled || busy}>{busy ? "Считаем…" : "Проверить достижимость цели"}</button></div>
        {plan ? <div className={`planner-result ${plan.feasible ? "feasible" : "constrained"}`}>
          <div className="planner-result-copy"><p className="eyebrow">{plan.feasible ? "Цель достижима" : "Есть ограничение"}</p><h3>{plan.headline}</h3><p>{plan.narrative}</p></div>
          <div className="planner-metrics"><div><small>Достижимо клиентов</small><strong>{fmt(plan.achievable_customers, 0)}</strong></div><div><small>Нужный бюджет</small><strong>{fmt(plan.required_budget)}</strong></div><div><small>Бюджет в день</small><strong>{fmt(plan.recommended_daily_budget)}</strong></div><div><small>Оценочный срок</small><strong>{plan.estimated_days === null ? "—" : `${fmt(plan.estimated_days, 1)} дн.`}</strong></div><div><small>Дефицит клиентов</small><strong>{fmt(plan.customer_gap, 0)}</strong></div><div><small>Дефицит бюджета</small><strong>{fmt(plan.budget_gap)}</strong></div></div>
          {economics ? <div className="planner-economics"><span>CAC <strong>{fmt(economics.blended_cac)}</strong></span><span>LTV/CAC <strong>{fmt(economics.ltv_to_cac_ratio, 2)}</strong></span><span>Окупаемость <strong>{fmt(economics.payback_months, 1)} мес.</strong></span><span>Экономика <strong>{economics.sustainable ? "устойчивая" : "требует правки"}</strong></span></div> : null}
          {Array.isArray(plan.recommendations) && plan.recommendations.length ? <div className="planner-recommendations"><h4>Что изменить</h4>{plan.recommendations.slice(0, 3).map((item) => <div key={`${item.kind}-${item.priority}`}><strong>{item.title}</strong><p>{item.description}</p></div>)}</div> : null}
          <p className="planner-disclaimer">Источник цифр в этом блоке — введённые вами предположения. Это не подтверждённые показатели бизнеса и не обещание результата.</p>
        </div> : null}
      </article>
    </section>
  );
}
