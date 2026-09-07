import { useCallback, useEffect, useMemo, useState } from "react";
import "./BusinessIntelligencePanel.css";

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

function money(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString("ru-RU", { maximumFractionDigits: 2 }) : "—";
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

export function BusinessIntelligencePanel({ enabled, initialGoal, onLoad, onRunGoal }) {
  const [snapshot, setSnapshot] = useState({ analytics: null, memory: null, recentRuns: [], errors: [] });
  const [loading, setLoading] = useState(Boolean(enabled));
  const [loadError, setLoadError] = useState("");
  const [goal, setGoal] = useState(initialGoal || "Улучшить результаты бизнеса");
  const [goalBusy, setGoalBusy] = useState(false);
  const [goalError, setGoalError] = useState("");
  const [goalResult, setGoalResult] = useState(null);

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
  const retention = business.retention || {};
  const decisions = business.decisions || {};
  const funnel = business.funnel || {};
  const diagnosis = business.diagnosis || {};
  const memory = snapshot.memory || {};
  const outcome = useMemo(() => goalResult ? goalOutcome(goalResult) : null, [goalResult]);

  const runGoal = async () => {
    const clean = goal.trim();
    if (!clean || !enabled || !onRunGoal) return;
    setGoalBusy(true);
    setGoalError("");
    setGoalResult(null);
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

      <div className="intelligence-metrics" aria-label="Ключевые показатели бизнеса">
        <article><small>Состояние</small><strong>{dashboard.overall_state ? humanText(dashboard.overall_state) : "Пока мало данных"}</strong><span>{Number.isFinite(Number(dashboard.overall_score)) ? `${Math.round(Number(dashboard.overall_score) * 100)} / 100` : "—"}</span></article>
        <article><small>Выручка по событиям</small><strong>{money(revenue.revenue_total)}</strong><span>успешных оплат: {metric(revenue.purchase_success_count)}</span></article>
        <article><small>Возврат клиентов</small><strong>{percent(retention.retention_ratio)}</strong><span>вернулось: {metric(retention.returning_users)}</span></article>
        <article><small>Исполнение решений</small><strong>{percent(decisions.execution_ratio)}</strong><span>заблокировано: {percent(decisions.blocked_ratio)}</span></article>
        <article><small>Конверсия в покупку</small><strong>{percent(funnel.visitor_to_purchase_rate)}</strong><span>клиентов в событиях: {metric(funnel.visitors)}</span></article>
      </div>

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
        {outcome ? <div className={`goal-outcome ${outcome.kind}`} role="status"><strong>{outcome.title}</strong><p>{outcome.text}</p>{goalResult?.steps?.[0]?.action ? <small>Следующий шаг: {humanText(goalResult.steps[0].action)}</small> : null}<details><summary>Техническое доказательство решения</summary><pre>{JSON.stringify(goalResult, null, 2)}</pre></details></div> : null}
      </article>
    </section>
  );
}
