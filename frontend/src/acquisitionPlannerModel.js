export const ACQUISITION_DEFAULTS = {
  target_customers: 10,
  total_budget: 1000,
  daily_budget: 100,
  target_days: 30,
  cost_per_entry: 2,
  conversion_percent: 10,
  sales_cycle_days: 7,
  gross_margin_ltv: 300,
  expected_monthly_margin_per_customer: 20
};

export const ACQUISITION_PRIMARY_FIELDS = [
  ["target_customers", "Новых клиентов", "Сколько клиентов хотите получить", 1, 10000, 1],
  ["total_budget", "Общий бюджет", "Сколько готовы вложить", 0, 1000000, 10],
  ["target_days", "Срок, дней", "За сколько дней хотите прийти к цели", 1, 3650, 1]
];

export const ACQUISITION_ADVANCED_FIELDS = [
  ["daily_budget", "Бюджет в день", "Если есть жёсткий дневной лимит", 0, 100000, 1],
  ["cost_per_entry", "Цена входящего лида", "Средняя стоимость одного входа в воронку", 0.01, 10000, 0.01],
  ["conversion_percent", "Конверсия лид → клиент, %", "Ваше текущее или ожидаемое значение", 0.01, 100, 0.01],
  ["sales_cycle_days", "Цикл сделки, дней", "Среднее время от лида до покупки", 0, 3650, 1],
  ["gross_margin_ltv", "Маржинальная ценность клиента", "Ожидаемая валовая маржа за всё время работы с клиентом", 0, 1000000, 1],
  ["expected_monthly_margin_per_customer", "Маржа с клиента в месяц", "Нужна для оценки срока окупаемости", 0, 100000, 1]
];

export const ACQUISITION_FIELDS = [...ACQUISITION_PRIMARY_FIELDS, ...ACQUISITION_ADVANCED_FIELDS];

export function isAcquisitionFormValid(form) {
  return ACQUISITION_FIELDS.every(([key, , , min, max, step]) => {
    const raw = form[key];
    if (raw === null || raw === undefined || String(raw).trim() === "") return false;
    const value = Number(raw);
    if (!Number.isFinite(value) || value < min || value > max) return false;
    const steps = (value - min) / step;
    return Math.abs(steps - Math.round(steps)) < 1e-8;
  });
}

export function acquisitionPayload(form) {
  if (!isAcquisitionFormValid(form)) throw new TypeError("invalid acquisition assumptions");
  return {
    target_customers: Number(form.target_customers),
    total_budget: Number(form.total_budget),
    daily_budget: Number(form.daily_budget),
    target_days: Number(form.target_days),
    cost_per_entry: Number(form.cost_per_entry),
    gross_margin_ltv: Number(form.gross_margin_ltv),
    expected_monthly_margin_per_customer: Number(form.expected_monthly_margin_per_customer),
    stages: [{
      name: "lead_to_customer",
      conversion_rate: Number(form.conversion_percent) / 100,
      avg_stage_days: Number(form.sales_cycle_days),
      touchpoints: 1
    }]
  };
}

export function formatMetric(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: digits }).format(Number(value));
}
