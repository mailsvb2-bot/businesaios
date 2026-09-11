import { useMemo, useState } from "react";
import "./DiscoverBuildMeasurePanel.css";

function money(value) {
  if (!value || !Number.isSafeInteger(Number(value.amount_minor)) || !value.currency) return "—";
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: value.currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(value.amount_minor) / 100);
  } catch {
    return `${Number(value.amount_minor) / 100} ${value.currency}`;
  }
}

function percent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%` : "—";
}

export function DiscoverBuildMeasurePanel({ enabled, onRecordObservation, onDiscover, onBuild, onMeasure, onRunBlueprintDecision, onPrepareAction }) {
  const [snapshot, setSnapshot] = useState(null);
  const [selected, setSelected] = useState(null);
  const [blueprint, setBlueprint] = useState(null);
  const [decisionResult, setDecisionResult] = useState(null);
  const [measurement, setMeasurement] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [statusText, setStatusText] = useState("");
  const [observationRequestKey, setObservationRequestKey] = useState(() => crypto.randomUUID());
  const [buildRequestKey, setBuildRequestKey] = useState(() => crypto.randomUUID());
  const [decisionRequestKey, setDecisionRequestKey] = useState(() => crypto.randomUUID());
  const [observation, setObservation] = useState({
    process_key: "", occurred_at: "", manual_minutes: "", actor_cost_per_hour: "",
    direct_loss: "", revenue_at_risk: "", currency: "RUB", automation_fit: "0.7", operational_risk: "0.3",
  });

  const opportunities = Array.isArray(snapshot?.opportunities) ? snapshot.opportunities : [];
  const selectedOpportunity = useMemo(
    () => opportunities.find((item) => item.opportunity_id === selected) || opportunities[0] || null,
    [opportunities, selected],
  );

  function rotateAfterDefinitiveError(error, setter) {
    const status = Number(error?.httpStatus || 0);
    if (error?.serverResponded === true && status >= 400 && status < 500 && status !== 408) setter(crypto.randomUUID());
  }

  async function recordObservation() {
    if (!enabled || !onRecordObservation || !observation.process_key.trim() || !observation.occurred_at) return;
    setBusy("record"); setError(""); setStatusText("");
    const minor = (value) => String(value || "").trim() === "" ? null : Math.round(Number(value) * 100);
    try {
      await onRecordObservation({
        process_key: observation.process_key.trim(),
        occurred_at: new Date(observation.occurred_at).toISOString(),
        manual_minutes: Number(observation.manual_minutes || 0),
        actor_cost_per_hour_minor: minor(observation.actor_cost_per_hour),
        direct_loss_minor: minor(observation.direct_loss),
        revenue_at_risk_minor: minor(observation.revenue_at_risk),
        currency: observation.currency.trim().toUpperCase(),
        automation_fit: Number(observation.automation_fit),
        operational_risk: Number(observation.operational_risk),
      }, observationRequestKey);
      setObservationRequestKey(crypto.randomUUID());
      setStatusText("Факт сохранён как owner-asserted evidence с серверным ID. Он не считается автоматически подтверждённой финансовой потерей.");
      setObservation((current) => ({ ...current, occurred_at: "", manual_minutes: "", direct_loss: "", revenue_at_risk: "" }));
      const result = await onDiscover?.();
      if (result) {
        setSnapshot(result);
        const first = Array.isArray(result.opportunities) ? result.opportunities[0] : null;
        setSelected(first?.opportunity_id || null);
      }
    } catch (requestError) {
      rotateAfterDefinitiveError(requestError, setObservationRequestKey);
      setError("Факт не сохранён: проверьте дату, числа и валюту. При неопределённом сетевом ответе повтор использует тот же idempotency key.");
    } finally { setBusy(""); }
  }

  async function discover() {
    if (!enabled || !onDiscover) return;
    setBusy("discover"); setError(""); setStatusText(""); setBlueprint(null); setDecisionResult(null); setMeasurement(null);
    try {
      const result = await onDiscover();
      setSnapshot(result || null);
      const first = Array.isArray(result?.opportunities) ? result.opportunities[0] : null;
      setSelected(first?.opportunity_id || null);
    } catch {
      setError("Не удалось безопасно прочитать процессные факты. Никаких действий не выполнено.");
    } finally { setBusy(""); }
  }

  async function build() {
    if (!selectedOpportunity || !onBuild) return;
    setBusy("build"); setError(""); setStatusText(""); setDecisionResult(null); setMeasurement(null);
    try {
      const result = await onBuild(selectedOpportunity, {
        owner_goal: `Снизить потери процесса ${selectedOpportunity.process_key}, сохраняя действующие ограничения безопасности`,
        expected_coverage: 0.5,
      }, buildRequestKey);
      setBuildRequestKey(crypto.randomUUID());
      setDecisionRequestKey(crypto.randomUUID());
      setBlueprint(result || null);
    } catch (requestError) {
      rotateAfterDefinitiveError(requestError, setBuildRequestKey);
      setError("Не удалось подготовить blueprint. Исполнение и approval не создавались.");
    } finally { setBusy(""); }
  }

  async function sendGoal() {
    const blueprintId = String(blueprint?.blueprint?.blueprint_id || "").trim();
    if (!blueprintId || !onRunBlueprintDecision) return;
    setBusy("decision"); setError(""); setStatusText(""); setDecisionResult(null); setMeasurement(null);
    try {
      const result = await onRunBlueprintDecision(blueprintId, decisionRequestKey);
      setDecisionRequestKey(crypto.randomUUID());
      setDecisionResult(result || null);
      setStatusText("Цель передана существующему DecisionCore. Это ещё не доказательство исполнения вмешательства.");
    } catch (requestError) {
      rotateAfterDefinitiveError(requestError, setDecisionRequestKey);
      setError("DecisionCore не принял цель. При неопределённом сетевом ответе повтор не создаст новый запрос; внешнее действие не подтверждено.");
    } finally { setBusy(""); }
  }

  async function prepareAction() {
    if (!decisionResult || !onPrepareAction) return;
    setBusy("action"); setError(""); setStatusText("");
    try {
      await onPrepareAction(decisionResult);
      setStatusText("Черновик передан в существующий Центр действий. Получатель и внешнее выполнение по-прежнему требуют обычных проверок и approval.");
    } catch {
      setError("Этот результат нельзя безопасно передать в Центр действий. Никакое внешнее действие не выполнено.");
    } finally { setBusy(""); }
  }

  async function measure() {
    const blueprintId = blueprint?.blueprint?.blueprint_id;
    if (!blueprintId || !onMeasure || !decisionResult) return;
    setBusy("measure"); setError(""); setStatusText("");
    try {
      const result = await onMeasure(blueprintId);
      setMeasurement(result || null);
      if (result?.status === "intervention_not_verified") {
        setStatusText("Измерение ещё не открыто: сервер пока не подтвердил фактическое вмешательство/исполнение, связанное с этим blueprint.");
      } else if (result?.status === "insufficient_after_evidence") {
        setStatusText("Вмешательство подтверждено, но после него пока недостаточно данных для честного сравнения.");
      }
    } catch {
      setError("Измерение отклонено из-за недостатка или несогласованности серверных доказательств. Нули не подставлялись.");
    } finally { setBusy(""); }
  }

  const decisionStep = Array.isArray(decisionResult?.steps) ? decisionResult.steps[0] : null;
  const canPrepareAction = Boolean(
    onPrepareAction && decisionResult?.run_id && decisionStep?.decision_id && decisionStep?.action_id
      && decisionStep?.action === "send_message@v1" && !decisionStep?.executed
  );
  const roi = measurement?.status === "ok" ? measurement?.measurement || null : null;

  return (
    <section className="dbm-panel" aria-labelledby="dbm-title">
      <div className="dbm-heading">
        <div>
          <p className="eyebrow">Discover → Build → Measure</p>
          <h3 id="dbm-title">Где бизнес теряет время и деньги</h3>
          <p>Сначала подтверждённые факты, затем безопасный blueprint, затем измерение только после серверно подтверждённого вмешательства.</p>
        </div>
        <button type="button" className="ghost small" disabled={!enabled || Boolean(busy)} onClick={discover}>
          {busy === "discover" ? "Ищем…" : "Найти потери"}
        </button>
      </div>

      <div className="dbm-steps" aria-label="Этапы Discover Build Measure">
        <span className={snapshot ? "done" : "active"}>1. Discover</span>
        <span className={blueprint ? "done" : snapshot ? "active" : ""}>2. Build</span>
        <span className={roi ? "done" : decisionResult ? "active" : ""}>3. Measure</span>
      </div>

      <details className="dbm-evidence-entry">
        <summary>Добавить реальный факт о повторяющемся процессе</summary>
        <p>Введите одно фактическое выполнение процесса. BusinessAIOS выдаст evidence ID на сервере; браузер не задаёт доверие, tenant или business.</p>
        <div className="dbm-form-grid">
          <label><span>Процесс</span><input value={observation.process_key} onChange={(e) => setObservation({ ...observation, process_key: e.target.value })} placeholder="например, follow_up_клиента" /></label>
          <label><span>Когда произошло</span><input type="datetime-local" value={observation.occurred_at} onChange={(e) => setObservation({ ...observation, occurred_at: e.target.value })} /></label>
          <label><span>Ручное время, мин</span><input type="number" min="0" value={observation.manual_minutes} onChange={(e) => setObservation({ ...observation, manual_minutes: e.target.value })} /></label>
          <label><span>Стоимость часа сотрудника</span><input type="number" min="0" step="0.01" value={observation.actor_cost_per_hour} onChange={(e) => setObservation({ ...observation, actor_cost_per_hour: e.target.value })} /></label>
          <label><span>Прямая потеря</span><input type="number" min="0" step="0.01" value={observation.direct_loss} onChange={(e) => setObservation({ ...observation, direct_loss: e.target.value })} /></label>
          <label><span>Деньги под риском</span><input type="number" min="0" step="0.01" value={observation.revenue_at_risk} onChange={(e) => setObservation({ ...observation, revenue_at_risk: e.target.value })} /></label>
          <label><span>Валюта</span><input value={observation.currency} maxLength={3} onChange={(e) => setObservation({ ...observation, currency: e.target.value })} /></label>
          <label><span>Пригодность к автоматизации 0–1</span><input type="number" min="0" max="1" step="0.1" value={observation.automation_fit} onChange={(e) => setObservation({ ...observation, automation_fit: e.target.value })} /></label>
          <label><span>Операционный риск 0–1</span><input type="number" min="0" max="1" step="0.1" value={observation.operational_risk} onChange={(e) => setObservation({ ...observation, operational_risk: e.target.value })} /></label>
        </div>
        <p className="dbm-note">Стоимость и потери здесь — утверждение владельца. Они не становятся verified money без соответствующего качества evidence.</p>
        <button type="button" className="secondary" disabled={!enabled || Boolean(busy) || !observation.process_key.trim() || !observation.occurred_at} onClick={recordObservation}>
          {busy === "record" ? "Сохраняем…" : "Сохранить факт"}
        </button>
      </details>

      {error ? <div className="error-box inline-error" role="alert">{error}</div> : null}
      {statusText ? <div className="dbm-note" role="status">{statusText}</div> : null}

      {snapshot?.status === "insufficient_process_evidence" ? (
        <div className="dbm-empty">Пока недостаточно серверных процессных фактов. Система не придумывает потери.</div>
      ) : null}

      {opportunities.length ? (
        <div className="dbm-grid">
          <aside className="dbm-list" aria-label="Найденные возможности">
            {opportunities.map((item) => (
              <button
                type="button"
                key={item.opportunity_id}
                className={selectedOpportunity?.opportunity_id === item.opportunity_id ? "selected" : ""}
                onClick={() => { setSelected(item.opportunity_id); setBuildRequestKey(crypto.randomUUID()); setDecisionRequestKey(crypto.randomUUID()); setBlueprint(null); setDecisionResult(null); setMeasurement(null); }}
              >
                <strong>{item.process_key}</strong>
                <span>Приоритет {item.priority_score} / 100 · уверенность {percent(item.confidence)}</span>
              </button>
            ))}
          </aside>

          {selectedOpportunity ? (
            <article className="dbm-card">
              <p className="eyebrow">Discover</p>
              <h4>Найдена повторяющаяся потеря</h4>
              <div className="dbm-metrics">
                <div><small>Ручное время / 30 дней</small><strong>{selectedOpportunity.manual_minutes_per_30d ?? "—"} мин</strong></div>
                <div><small>Подтверждённая потеря / 30 дней</small><strong>{money(selectedOpportunity.realized_loss_per_30d)}</strong></div>
                <div><small>Деньги под риском</small><strong>{money(selectedOpportunity.revenue_at_risk_per_30d)}</strong></div>
                <div><small>Качество денег</small><strong>{selectedOpportunity.money_status || "—"}</strong></div>
              </div>
              <p className="dbm-note">Деньги под риском показываются отдельно и не считаются уже потерянными.</p>
              <button type="button" disabled={Boolean(busy)} onClick={build}>
                {busy === "build" ? "Готовим…" : "Подготовить безопасный план"}
              </button>
            </article>
          ) : null}
        </div>
      ) : null}

      {blueprint?.blueprint ? (
        <article className="dbm-card dbm-build-card">
          <p className="eyebrow">Build</p>
          <h4>{blueprint.blueprint.goal}</h4>
          <p>Стартовый режим: <strong>{blueprint.blueprint.initial_stage}</strong>. Blueprint не является исполняемым действием и сам не повышает автономность.</p>
          <div className="dbm-actions">
            <button type="button" className="secondary" disabled={!onRunBlueprintDecision || Boolean(busy)} onClick={sendGoal}>
              {busy === "decision" ? "Передаём…" : "Передать цель в DecisionCore"}
            </button>
            {canPrepareAction ? <button type="button" disabled={Boolean(busy)} onClick={prepareAction}>{busy === "action" ? "Передаём…" : "В Центр действий"}</button> : null}
            <button type="button" className="ghost" disabled={!decisionResult || Boolean(busy)} onClick={measure}>
              {busy === "measure" ? "Проверяем доказательства…" : "Проверить результат"}
            </button>
          </div>
          <small>Даже после DecisionCore Measure откроется только при серверно подтверждённом intervention proof и фактах, возникших после него.</small>
        </article>
      ) : null}

      {roi ? (
        <article className="dbm-card dbm-measure-card">
          <p className="eyebrow">Measure</p>
          <h4>Что изменилось после подтверждённого вмешательства</h4>
          <div className="dbm-metrics">
            <div><small>Сэкономлено ручного времени / 30 дней</small><strong>{roi.manual_minutes_saved_per_30d ?? "—"} мин</strong></div>
            <div><small>Валовая экономия / 30 дней</small><strong>{money(roi.gross_savings_per_30d)}</strong></div>
            <div><small>Стоимость автоматизации / 30 дней</small><strong>{money(roi.intervention_cost_per_30d)}</strong></div>
            <div><small>Чистый эффект / 30 дней</small><strong>{money(roi.net_benefit_per_30d)}</strong></div>
          </div>
          <div className="dbm-proof">
            <strong>Доказательность: {roi.evidence_grade}</strong>
            <span>{roi.copy?.causal_note || "—"}</span>
          </div>
        </article>
      ) : null}
    </section>
  );
}
