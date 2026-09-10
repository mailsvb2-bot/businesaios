const NEXT_STEP_COPY = Object.freeze({
  low_offer_ctr: {
    title: "Усилить предложение и путь к покупке",
    goal: "Найти безопасный способ увеличить переходы по предложению и конверсию в покупку на основе фактов моего бизнеса",
    why: "Аналитика видит мало переходов после показа предложения.",
    surfaceId: "acquisition-planner-title",
    surfaceLabel: "Открыть расчёт привлечения"
  },
  low_retention: {
    title: "Вернуть больше клиентов",
    goal: "Найти безопасный способ увеличить повторные продажи и возврат клиентов на основе истории контактов моего бизнеса",
    why: "Аналитика видит низкую долю возвращающихся клиентов.",
    surfaceId: "business-customers-title",
    surfaceLabel: "Открыть клиентов"
  },
  high_blocked_decision_ratio: {
    title: "Разобрать, почему решения блокируются",
    goal: "Разобрать причины частых блокировок решений и предложить безопасный путь улучшения без ослабления правил и подтверждений владельца",
    why: "Заметная доля решений останавливается действующими правилами безопасности.",
    surfaceId: "business-operations-title",
    surfaceLabel: "Открыть центр действий"
  },
  latency_degraded: {
    title: "Разобрать замедление системы",
    goal: "Определить причину ухудшения скорости BusinessAIOS и предложить безопасный следующий шаг без внешних действий",
    why: "В подтверждённых измерениях скорость системы хуже обычной.",
    surfaceId: "business-intelligence-title",
    surfaceLabel: "Остаться в анализе"
  },
  latency_critical: {
    title: "Разобрать критическое замедление",
    goal: "Определить причину критической задержки BusinessAIOS и предложить безопасный план восстановления без внешних действий",
    why: "Подтверждённые измерения показывают критическую задержку.",
    surfaceId: "business-intelligence-title",
    surfaceLabel: "Остаться в анализе"
  },
  low_revenue_signal: {
    title: "Найти путь к подтверждённой выручке",
    goal: "Найти следующий безопасный шаг к росту подтверждённых покупок на основе текущей воронки и данных моего бизнеса",
    why: "За текущее окно пока мало подтверждённых сигналов успешной покупки.",
    surfaceId: "acquisition-planner-title",
    surfaceLabel: "Открыть расчёт привлечения"
  }
});

export function buildIntelligenceNextSteps(reasons) {
  if (!Array.isArray(reasons)) return [];
  const seen = new Set();
  return reasons.flatMap((reason) => {
    const key = String(reason || "");
    const step = NEXT_STEP_COPY[key];
    if (!step || seen.has(key)) return [];
    seen.add(key);
    return [{ reason: key, ...step }];
  }).slice(0, 3);
}
