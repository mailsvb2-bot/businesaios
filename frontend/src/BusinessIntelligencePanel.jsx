import { useCallback, useEffect, useMemo, useState } from "react";
import "./BusinessIntelligencePanel.css";
import { buildIntelligenceNextSteps } from "./intelligenceNextSteps.js";

const REASON_COPY = {
  low_offer_ctr: "Мало переходов после показа предложения",
  low_retention: "Мало клиентов возвращается повторно",
  high_blocked_decision_ratio: "Слишком много решений останавливается правилами безопасности",
  latency_degraded: "Ответы системы стали медленнее обычного",
  latency_critical: "Система отвечает слишком медленно",
  low_revenue_signal: "Пока мало подтверждённых сигналов выручки",
  no_major_issues_detected: "Крупных проблем по доступным данным не обнаружено"
};

const HIGHLIGHT_COPY = {
  offer_ctr_not_collapsed: "Воронка показа предложения не выглядит обрушенной",
  returning_users_present: "Есть возвращающиеся клиенты",
  execution_path_operational: "Контур исполнения решений работает",
  latency_within_budget: "Скорость системы в рабочем диапазоне",
  revenue_signal_present: "Есть подтверждённый сигнал выручки"
};

function percent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%` : "—";
}

function moneyFromMinor(value, currency = "") {
  const minor = Number(value);
  const normalizedCurrency = String(currency || "").trim().toUpperCase();
  if (!Number.isSafeInteger(minor) || !normalizedCurrency) return "—";
  try {
    const formatter = new Intl.NumberFormat("ru-RU", { style: "currency", currency: normalizedCurrency, minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return formatter.format(minor / 100);
  } catch { return "—"; }
}

function metric(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString("ru-RU", { maximumFractionDigits: 2 }) : "—";
}

function humanText(value, dictionary = {}) {
  const key = String(value || "");
  return dictionary[key] || key.replaceAll("_", " ");
}

function goalOutcome(result) {
  const step = Array.isArray(result?.steps) ? result.steps[0] : null;
  const status = String(step?.status || "").toLowerCase();
  if (status === "approval_required" || status === "operator_required") {
    return { kind: "approval", title: "Нужно ваше подтверждение", text: "DecisionCore подготовил следующий шаг, но эта кнопка не выполняет внешнее действие." };
  }
  if (status === "blocked_by_policy") {
    return { kind: "blocked", title: "Остановлено правилами безопасности", text: "Система не выполнила действие, которое не прошло действующие ограничения." };
  }
  if (result?.completed) {
    return { kind: "done", title: "Шаг разобран", text: "DecisionCore завершил разбор этого шага и сохранил результат в канонической памяти бизнеса." };
  }
  return { kind: "neutral", title: "Результат получен", text: "DecisionCore вернул следующий шаг. Эта кнопка не выполняет внешние действия." };
}

function PatternList({ title, items, empty }) {
  return <div className="intelligence-list"><strong>{title}</strong>{items?.length ? <ul>{items.slice(0, 5).map((item) => <li key={String(item)}>{humanText(item)}</li>)}</ul> : <small>{empty}</small>}</div>;
}

export function BusinessIntelligencePanel({ enabled, initialGoal, onLoad, onRunGoal, onPrepareAction, onOpenSurface }) {
  const [snapshot, setSnapshot] = useState({ analytics: null, memory: null, recentRuns: [], errors: [] });
  const [loading, setLoading] = useState(Boolean(enabled));
  const [loadError, setLoadError] = useState("");
  const [goal, setGoal] = useState(initialGoal || "Улучшить результаты бизнеса");
  const [goalBusy, setGoalBusy] = useState(false);
  const [goalError, setGoalError] = useState("");
  const [goalResult, setGoalResult] = useState(null);
  const [handoffBusy, setHandoffBusy] = useState(false);
  const [handoffError, setHandoffError] = useState("");

  const refresh = useCallback(async () => {
    if (!enabled || !onLoad) return;
    setLoading(true);
    setLoadError("");
    try {
      const next = await onLoad();
      setSnapshot({ analytics: next?.analytics || null, memory: next?.memory || null, recentRuns: Array.isArray(next?.recentRuns) ? next.recentRuns : [], errors: Array.isArray(next?.errors) ? next.errors : [] });
    } catch {
      setLoadError("Не удалось обновить анализ. Остальные функции кабинета продолжают работать.");
    } finally {
      setLoading(false);
    }
  }, [enabled, onLoad]);

  useEffect(() => { void refresh(); }, [refresh]);

  const dashboard = snapshot.analytics?.dashboard || {};
  const business = snapshot.analytics?.business || {};
  const revenue = business.revenue || {};
  const revenueMetadata = business.metadata || {};
  const revenueCurrency = String(revenueMetadata.revenue_currency || "").trim().toUpperCase();
  const revenueMoneyStatus = String(revenueMetadata.revenue_money_status || "unverified");
  const revenueMinorTotal = Number(revenueMetadata.revenue_minor_total);
  const revenueSuccessCount = Number(revenue.purchase_success_count);
  const revenueWindowDays = Number.isFinite(Number(business.window_days)) ? Number(business.window_days) : 30;
  const revenueAmountReady = Boolean(snapshot.analytics && Number.isSafeInteger(revenueSuccessCount) && revenueSuccessCount > 0 && revenueMoneyStatus === "verified_minor_units" && revenueCurrency && Number.isSafeInteger(revenueMinorTotal));
  const revenueTruth = !snapshot.analytics
    ? "Финансовая аналитика сейчас недоступна. BusinessAIOS не подставляет вместо неё нули."
    : !Number.isFinite(revenueSuccessCount) || revenueSuccessCount <= 0
      ? "За это окно событий успешной покупки нет. Это не доказывает нулевую выручку вне подключённых событий."
      : revenueMoneyStatus === "mixed_currency"
        ? "В подтверждённых событиях покупки несколько валют. BusinessAIOS не складывает их в одну фиктивную сумму."
        : !revenueAmountReady
          ? "События покупки есть, но у них нет полного строгого контракта amount_minor + currency. Сумма и средний чек скрыты, чтобы не перепутать рубли с копейками или разные денежные единицы."
          : `Все денежные события этого окна имеют строгую сумму в minor units и одну валюту: ${revenueCurrency}.`;
  const retention = business.retention || {};
  const decisions = business.decisions || {};
  const funnel = business.funnel || {};
  const diagnosis = business.diagnosis || {};
  const memory = snapshot.memory || {};
  const outcome = useMemo(() => goalResult ? goalOutcome(goalResult) : null, [goalResult]);
  const goalStep = Array.isArray(goalResult?.steps) ? goalResult.steps[0] : null;
  const handoffEligible = Boolean(goalResult?.run_id && goalStep?.action === "send_message@v1" && !goalStep?.executed && !goalStep?.verified);
  const nextSteps = useMemo(() => buildIntelligenceNextSteps(diagnosis.reasons || []), [diagnosis.reasons]);

  const runGoal = async (suggestedGoal = "") => {
    const clean = String(suggestedGoal || goal).trim();
    if (!clean || !enabled || !onRunGoal) return;
    if (suggestedGoal) setGoal(clean);
    setGoalBusy(true);
    setGoalError("");
    setGoalResult(null);
    setHandoffError("");
    try {
      const result = await onRunGoal(clean);
      setGoalResult(result);
      await refresh();
    } catch {
      setGoalError("Не удалось разобрать цель. Ничего внешнему сервису не отправлено.");
    } finally {
      setGoalBusy(false);
    }
  };

  const prepareGoalAction = async () => {
    if (!handoffEligible || !onPrepareAction || !goalResult) return;
    setHandoffBusy(true);
    setHandoffError("");
    try {
      await onPrepareAction(goalResult);
    } catch {
      setHandoffError("Не удалось безопасно перенести решение в Центр действий. Ничего не отправлено и approval не создан.");
    } finally {
      setHandoffBusy(false);
    }
  };

  return (
    <section className="panel intelligence-panel" aria-labelledby="business-intelligence-title">
      <div className="panel-title-row intelligence-title-row">
        <div><p className="eyebrow">Анализ и память</p><h2 id="business-intelligence-title">Что происходит и что делать дальше</h2></div>
        <button type="button" className="ghost small" disabled={!enabled || loading} onClick={refresh}>{loading ? "Обновляем…" : "Обновить факты"}</button>
      </div>
      <p className="muted-text">Здесь используются существующие Analytics, Business Memory и DecisionCore BusinessAIOS. Отдельной памяти, второй аналитики или обходного исполнителя кабинет не создаёт.</p>

      {loadError ? <div className="error-box inline-error" role="alert">{loadError}</div> : null}
      {snapshot.errors.length ? <div className="intelligence-warning" role="status">Часть данных сейчас недоступна: {snapshot.errors.join(", ")}. Доступные факты показаны ниже.</div> : null}
      {loading && !snapshot.analytics && !snapshot.memory ? <div className="loading-box">Собираем факты из канонических данных бизнеса…</div> : null}

      <article className="money-cockpit" aria-labelledby="business-money-title">
        <div className="money-cockpit-head"><div><p className="eyebrow">Деньги</p><h3 id="business-money-title">Денежные факты</h3></div><span>Последние {revenueWindowDays} дней</span></div>
        <p className="muted-text">Здесь только успешные и неуспешные события покупки из существующей Business Analytics. Денежную сумму показываем лишь при строгом amount_minor + currency. Это не банковский баланс и не бухгалтерский P&amp;L.</p>
        <div className="money-metrics" aria-label="Подтверждённые финансовые показатели">
          <div><small>Сумма успешных оплат</small><strong>{revenueAmountReady ? moneyFromMinor(revenueMinorTotal, revenueCurrency) : "—"}</strong><span>{revenueAmountReady ? `строгий minor-unit контракт · ${revenueCurrency}` : "сумма только из строгих minor units одной валюты"}</span></div>
          <div><small>Успешные оплаты</small><strong>{metric(revenue.purchase_success_count)}</strong><span>событий успешной покупки</span></div>
          <div><small>Средний чек</small><strong>{revenueAmountReady ? moneyFromMinor(Math.round(revenueMinorTotal / revenueSuccessCount), revenueCurrency) : "—"}</strong><span>{revenueAmountReady ? "по событиям успешной покупки" : "не считаем без безопасной суммы"}</span></div>
          <div><small>Неуспешные оплаты</small><strong>{metric(revenue.purchase_failed_count)}</strong><span>зафиксированных неуспешных попыток</span></div>
        </div>
        <div className={`money-truth-note ${revenueAmountReady ? "verified" : "caution"}`} role="status"><strong>{revenueAmountReady ? "Сумма проверена по валюте" : "Почему сумма может быть скрыта"}</strong><span>{revenueTruth}</span></div>
        <div className="money-scope-grid">
          <div><strong>Что уже считаем</strong><span>События успешной/неуспешной покупки и денежную сумму — только когда amount_minor и currency однозначны для всего окна.</span></div>
          <div><strong>Что пока не выдаём за факт</strong><span>Возвраты и chargeback этим числом не вычитаются. Остаток на счетах, расходы, налоги, чистую прибыль и долг тоже не показываем без подтверждённого пользовательского источника.</span></div>
        </div>
      </article>

      <div className="intelligence-metrics" aria-label="Ключевые показатели бизнеса">
        <article><small>Состояние</small><strong>{dashboard.overall_state ? humanText(dashboard.overall_state) : "Пока мало данных"}</strong><span>{Number.isFinite(Number(dashboard.overall_score)) ? `${Math.round(Number(dashboard.overall_score) * 100)} / 100` : "—"}</span></article>
        <article><small>Возврат клиентов</small><strong>{percent(retention.retention_ratio)}</strong><span>вернулось: {metric(retention.returning_users)}</span></article>
        <article><small>Исполнение решений</small><strong>{percent(decisions.execution_ratio)}</strong><span>заблокировано: {percent(decisions.blocked_ratio)}</span></article>
        <article><small>Конверсия в покупку</small><strong>{percent(funnel.visitor_to_purchase_rate)}</strong><span>клиентов в событиях: {metric(funnel.visitors)}</span></article>
      </div>

      {nextSteps.length ? <article className="intelligence-next-steps" aria-labelledby="business-next-steps-title">
        <div className="next-steps-heading"><div><p className="eyebrow">Следующие шаги</p><h3 id="business-next-steps-title">Что имеет смысл разобрать сейчас</h3></div><span>{nextSteps.length} по текущим фактам</span></div>
        <p className="muted-text">Шаги появляются только из текущих диагнозов Analytics. Нажатие «Разобрать» передаёт цель существующему DecisionCore в режиме советника; оно не отправляет сообщения, не меняет рекламу и не тратит деньги.</p>
        <div className="next-step-grid">{nextSteps.map((step) => <div className="next-step-card" key={step.reason}>
          <div><small>Почему сейчас</small><strong>{step.title}</strong><p>{step.why}</p></div>
          <div className="next-step-actions"><button type="button" className="primary small" disabled={!enabled || goalBusy} onClick={() => runGoal(step.goal)}>{goalBusy && goal === step.goal ? "Разбираем…" : "Разобрать с DecisionCore"}</button><button type="button" className="ghost small" disabled={!onOpenSurface} onClick={() => onOpenSurface?.(step.surfaceId)}>{step.surfaceLabel}</button></div>
        </div>)}</div>
      </article> : null}

      <div className="intelligence-columns">
        <article className="intelligence-card">
          <h3>Что видно по фактам</h3>
          <PatternList title="Риски" items={(diagnosis.reasons || []).filter((item) => item !== "no_major_issues_detected").map((item) => humanText(item, REASON_COPY))} empty="По доступным данным выраженных рисков пока нет." />
          <PatternList title="Хорошие сигналы" items={(diagnosis.highlights || []).map((item) => humanText(item, HIGHLIGHT_COPY))} empty="Нужно больше реальных событий, чтобы выделить устойчивые сильные стороны." />
        </article>

        <article className="intelligence-card">
          <h3>Что BusinessAIOS помнит</h3>
          <div className="memory-summary"><span><strong>{metric(memory.total_runs)}</strong><small>запусков</small></span><span><strong>{metric(memory.completed_runs)}</strong><small>завершено</small></span><span><strong>{metric(memory.failed_runs)}</strong><small>неудачных</small></span></div>
          <PatternList title="Повторяющиеся успехи" items={memory.recurring_wins || []} empty="Устойчивые успешные шаблоны ещё не накоплены." />
          <PatternList title="Повторяющиеся проблемы" items={memory.recurring_failures || []} empty="Повторяющиеся проблемы пока не обнаружены." />
          {snapshot.recentRuns.length ? <details><summary>Последние решения · {snapshot.recentRuns.length}</summary><div className="recent-runs">{snapshot.recentRuns.map((run, index) => <div key={String(run.run_id || run.id || index)}><strong>{String(run.goal || run.objective || `Запуск ${index + 1}`)}</strong><small>{humanText(run.stop_reason || run.status || "сохранён")}</small></div>)}</div></details> : null}
        </article>
      </div>

      <article className="intelligence-goal-card">
        <div><p className="eyebrow">DecisionCore</p><h3>Дайте системе цель обычными словами</h3><p>BusinessAIOS разберёт один следующий шаг в режиме анализа и плана. Эта кнопка не выполняет внешние действия.</p></div>
        <label>Что вы хотите улучшить?<textarea value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="Например: увеличить повторные продажи без роста рекламного бюджета" /></label>
        <div className="navigation-row"><button type="button" className="primary" disabled={!enabled || goalBusy || !goal.trim()} onClick={runGoal}>{goalBusy ? "Разбираем цель…" : "Разобрать цель"}</button><small className="helper-text">Эта кнопка не выполняет внешние действия.</small></div>
        {goalError ? <div className="error-box inline-error" role="alert">{goalError}</div> : null}
        {outcome ? <div className={`goal-outcome ${outcome.kind}`} role="status"><strong>{outcome.title}</strong><p>{outcome.text}</p>{goalStep?.action ? <small>Следующий шаг: {humanText(goalStep.action)}</small> : null}{handoffEligible ? <div className="goal-handoff"><button type="button" className="primary small" disabled={handoffBusy || !onPrepareAction} onClick={prepareGoalAction}>{handoffBusy ? "Проверяем решение…" : "Передать как черновик в Центр действий"}</button><small>BusinessAIOS сначала сверит run/decision/action с серверным ledger. Отправки и approval на этом шаге нет.</small></div> : null}{handoffError ? <div className="error-box inline-error" role="alert">{handoffError}</div> : null}<details><summary>Техническое доказательство решения</summary><pre>{JSON.stringify(goalResult, null, 2)}</pre></details></div> : null}
      </article>
    </section>
  );
}
