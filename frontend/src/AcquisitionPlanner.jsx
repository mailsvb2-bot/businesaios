import { useState } from "react";
import {
  ACQUISITION_ADVANCED_FIELDS,
  ACQUISITION_DEFAULTS,
  ACQUISITION_PRIMARY_FIELDS,
  acquisitionPayload,
  formatMetric as fmt,
  isAcquisitionFormValid
} from "./acquisitionPlannerModel.js";
import "./AcquisitionPlanner.css";

function renderFields(fields, form, update, disabled, valid) {
  return fields.map(([key, label, hint, min, max, step]) => (
    <label key={key}>
      {label}
      <input type="number" min={min} max={max} step={step} value={form[key]} onChange={update(key)} disabled={disabled} aria-invalid={!valid} />
      <small>{hint}</small>
    </label>
  ));
}

export function AcquisitionPlanner({ enabled, onEvaluate }) {
  const [form, setForm] = useState(ACQUISITION_DEFAULTS);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const valid = isAcquisitionFormValid(form);
  const update = (key) => (event) => {
    setForm((previous) => ({ ...previous, [key]: event.target.value }));
    setResult(null);
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
        ...form,
        daily_budget: Number(form.target_days) > 0 ? Number(form.total_budget) / Number(form.target_days) : 0
      };
      setResult(await onEvaluate(acquisitionPayload(effectiveForm)));
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
        <div className="planner-heading">
          <div>
            <p className="eyebrow">Быстрый расчёт</p>
            <h2 id="acquisition-planner-title">Сколько клиентов можно получить с вашим бюджетом?</h2>
            <p className="muted-text">Укажите цель, бюджет и срок. Остальные параметры можно уточнить при желании.</p>
          </div>
          <span className="privacy-badge">Только расчёт</span>
        </div>
        {!enabled ? <div className="planner-session-note">Расчёт временно недоступен: вход в кабинет завершился после перезагрузки страницы.</div> : null}
        {error ? <div className="planner-error">{error}</div> : null}
        <div className="planner-form planner-primary-form">{renderFields(ACQUISITION_PRIMARY_FIELDS, form, update, !enabled || busy, valid)}</div>
        <button type="button" className="ghost planner-advanced-toggle" onClick={() => setShowAdvanced((value) => !value)} disabled={!enabled || busy} aria-expanded={showAdvanced}>
          {showAdvanced ? "Скрыть дополнительные параметры" : "Уточнить расчёт вручную"}
        </button>
        {showAdvanced ? (
          <div className="planner-advanced-block">
            <p>Эти параметры необязательны для быстрого сценария. После подключения реальных данных BusinessAIOS сможет опираться на фактические показатели бизнеса.</p>
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
          <p className="planner-disclaimer">Источник цифр в этом блоке — введённые вами предположения. Это не подтверждённые показатели бизнеса и не обещание результата.</p>
        </div> : null}
      </article>
    </section>
  );
}
