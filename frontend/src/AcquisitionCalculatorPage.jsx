import { useMemo, useState } from "react";
import "./acquisition-calculator.css";

const INITIAL = {
  target_customers: 30,
  total_budget: 150000,
  daily_budget: 5000,
  target_days: 30,
  cost_per_entry: 800,
  conversion_percent: 12,
  sales_cycle_days: 7,
  gross_margin_ltv: 60000,
  expected_monthly_margin_per_customer: 12000,
  setup_cost: 0,
  max_cac_to_ltv_ratio: 0.33,
  payback_horizon_months: 12
};

const FIELDS = [
  ["target_customers", "Новых клиентов", "Сколько новых клиентов хотите получить", 1],
  ["total_budget", "Общий бюджет", "Сколько готовы вложить за весь период", 100],
  ["daily_budget", "Дневной бюджет", "Максимальный расход в день", 100],
  ["target_days", "Срок, дней", "За сколько дней хотите достичь цели", 1],
  ["cost_per_entry", "Стоимость входящего лида", "Средняя стоимость одного нового лида", 10],
  ["conversion_percent", "Конверсия лид → клиент, %", "Какой процент лидов обычно становится клиентами", 0.1],
  ["sales_cycle_days", "Цикл сделки, дней", "Среднее время от лида до покупки", 1],
  ["gross_margin_ltv", "Маржинальный LTV клиента", "Сколько валовой маржи приносит клиент за всё время", 100],
  ["expected_monthly_margin_per_customer", "Маржа с клиента в месяц", "Нужна для оценки срока окупаемости", 100],
  ["setup_cost", "Разовые расходы", "Настройка рекламы, подрядчики, внедрение", 100]
];

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatNumber(value, digits = 0) {
  return Number(value || 0).toLocaleString("ru-RU", { maximumFractionDigits: digits });
}

async function calculate(apiBase, form) {
  const payload = {
    target_customers: Math.max(0, Math.round(number(form.target_customers))),
    total_budget: Math.max(0, number(form.total_budget)),
    daily_budget: Math.max(0, number(form.daily_budget)),
    target_days: Math.max(0, number(form.target_days)),
    cost_per_entry: Math.max(0, number(form.cost_per_entry)),
    gross_margin_ltv: Math.max(0, number(form.gross_margin_ltv)),
    expected_monthly_margin_per_customer: Math.max(0, number(form.expected_monthly_margin_per_customer)),
    setup_cost: Math.max(0, number(form.setup_cost)),
    max_cac_to_ltv_ratio: number(form.max_cac_to_ltv_ratio),
    payback_horizon_months: Math.max(1, number(form.payback_horizon_months)),
    stages: [{
      name: "lead_to_customer",
      conversion_rate: Math.min(1, Math.max(0, number(form.conversion_percent) / 100)),
      avg_stage_days: Math.max(0, number(form.sales_cycle_days)),
      touchpoints: 1
    }]
  };
  const response = await fetch(`${apiBase.replace(/\/$/, "")}/public-site/acquisition/feasibility`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
  return data;
}

export function CalculatorLauncher() {
  return <a className="calculator-launcher" href="/calculator">Рассчитать клиентов</a>;
}

export function AcquisitionCalculatorPage({ apiBase }) {
  const [form, setForm] = useState(INITIAL);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const view = result?.view || null;
  const economics = result?.economics || null;
  const score = useMemo(() => Math.round(number(economics?.feasibility_score) * 100), [economics]);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await calculate(apiBase, form));
    } catch (err) {
      setResult(null);
      setError(err?.message || "Не удалось выполнить расчёт");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="calc-shell">
      <header className="calc-topbar">
        <a className="calc-brand" href="/"><span>B</span>BusinessAIOS</a>
        <a href="/">Вернуться в BusinessAIOS</a>
      </header>

      <section className="calc-hero">
        <p className="calc-eyebrow">Сценарный калькулятор привлечения</p>
        <h1>Сколько клиентов реально получить с вашим бюджетом?</h1>
        <p>Введите собственные предположения. BusinessAIOS посчитает достижимость цели, требуемый бюджет, срок и экономику CAC/LTV через тот же Acquisition Engine, который используется внутри продукта.</p>
        <div className="calc-truth">Это сценарный расчёт, а не подтверждённые метрики вашего бизнеса. Никаких денег и рекламных действий калькулятор не запускает.</div>
      </section>

      <section className="calc-layout">
        <form className="calc-panel calc-form" onSubmit={submit}>
          <div className="calc-panel-head"><div><p className="calc-eyebrow">Ваш сценарий</p><h2>Цель и экономика</h2></div><button type="button" className="calc-reset" onClick={() => { setForm(INITIAL); setResult(null); setError(""); }}>Сбросить</button></div>
          <div className="calc-fields">
            {FIELDS.map(([key, label, help, step]) => (
              <label key={key}><span>{label}</span><input type="number" min="0" step={step} value={form[key]} onChange={update(key)} /><small>{help}</small></label>
            ))}
          </div>
          <button className="calc-primary" type="submit" disabled={busy}>{busy ? "Считаем…" : "Рассчитать достижимость"}</button>
          {error ? <div className="calc-error">{error}</div> : null}
        </form>

        <section className="calc-panel calc-result" aria-live="polite">
          {!view ? (
            <div className="calc-empty"><div>◎</div><h2>Результат появится здесь</h2><p>Калькулятор не обещает продажи. Он показывает, что следует из введённых вами стоимости лида, конверсии, бюджета и экономики клиента.</p></div>
          ) : (
            <>
              <div className={`calc-verdict ${view.feasible ? "is-good" : "is-warning"}`}>
                <span>{view.feasible ? "Цель достижима по сценарию" : "В текущем сценарии цель не сходится"}</span>
                <strong>{score}%</strong>
              </div>
              <h2>{view.headline}</h2>
              <p className="calc-narrative">{view.narrative}</p>
              <div className="calc-metrics">
                <div><small>Достижимо клиентов</small><strong>{formatNumber(view.achievable_customers)}</strong></div>
                <div><small>Нужно бюджета</small><strong>{formatNumber(view.required_budget)}</strong></div>
                <div><small>Рекомендуемый бюджет/день</small><strong>{formatNumber(view.recommended_daily_budget)}</strong></div>
                <div><small>Оценка срока</small><strong>{formatNumber(view.estimated_days, 1)} дн.</strong></div>
                <div><small>Расчётный CAC</small><strong>{formatNumber(economics?.blended_cac)}</strong></div>
                <div><small>LTV / CAC</small><strong>{formatNumber(economics?.ltv_to_cac_ratio, 2)}×</strong></div>
              </div>
              {(view.customer_gap > 0 || view.budget_gap > 0) ? <div className="calc-gap">Не хватает: {view.customer_gap > 0 ? `${formatNumber(view.customer_gap)} клиентов` : ""}{view.customer_gap > 0 && view.budget_gap > 0 ? " · " : ""}{view.budget_gap > 0 ? `${formatNumber(view.budget_gap)} бюджета` : ""}</div> : null}
              {view.recommendations?.length ? <div className="calc-actions"><h3>Что изменить первым</h3>{view.recommendations.slice(0, 3).map((item) => <article key={`${item.kind}-${item.priority}`}><strong>{item.title}</strong><p>{item.description}</p></article>)}</div> : null}
              <div className="calc-cta"><div><strong>Хотите заменить предположения реальными данными?</strong><p>Подключите CRM, аналитику или другой read-only источник — тогда BusinessAIOS сможет опираться на фактическую воронку.</p></div><a href="/">Подключить BusinessAIOS</a></div>
              <small className="calc-disclaimer">{result.disclaimer}</small>
            </>
          )}
        </section>
      </section>
    </main>
  );
}
