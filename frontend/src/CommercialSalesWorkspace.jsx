import { useCallback, useEffect, useMemo, useState } from "react";

/** Truthful owner view of the canonical OrderStore and InvoiceRegistry. */
export function CommercialSalesWorkspace({ apiBase, apiKey, getJson }) {
  const url = apiBase.replace(/\/$/, "") + "/business-workspace/commercial/orders";
  const [orders, setOrders] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState("");

  const refresh = useCallback(async (signal) => {
    if (!apiKey) return;
    setBusy(true);
    setError("");
    try {
      const data = await getJson(url, { "X-API-Key": apiKey });
      if (signal?.aborted) return;
      if (!Array.isArray(data?.orders) ||
          data.orders.some((o) => !o.order_id || !o.invoice_id ||
            !Number.isSafeInteger(o.amount_minor) || o.amount_minor <= 0 ||
            !Number.isSafeInteger(o.paid_minor) || o.paid_minor < 0 ||
            o.paid_minor > o.amount_minor || !o.currency)) {
        throw new Error("Некорректное подтверждение счёта сервером");
      }
      setOrders(data.orders);
      setLoaded(true);
    } catch (reason) {
      if (!signal?.aborted) setError("Невозможно получить канонические заказы: " +
        (reason?.message || "ошибка сети") + ". Предыдущая информация может устареть.");
    } finally {
      if (!signal?.aborted) setBusy(false);
    }
  }, [apiKey, getJson, url]);

  useEffect(() => {
    const controller = new AbortController();
    setOrders([]);
    setSelectedId("");
    setLoaded(false);
    if (apiKey) void refresh(controller.signal);
    return () => controller.abort();
  }, [apiKey, refresh]);

  const selected = useMemo(
    () => orders.find((item) => item.order_id === selectedId) || null,
    [orders, selectedId]
  );
  const money = (minor, currency) => (minor / 100).toLocaleString("ru-RU", {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }) + " " + currency;

  const stateText = (o) => {
    if (o.status === "cancelled") return "Отменён";
    if (o.status === "fulfilled") return "Отмечен исполненным";
    if (o.invoice_status === "credited") return "Кредитован или возвращён";
    if (o.invoice_status === "paid") return "Оплачен в Billing (PSP ещё не сверена)";
    if (o.invoice_status === "partially_paid") return "Частично оплачен";
    if (o.invoice_status === "issued") return "Счёт выставлен, оплата не подтверждена";
    return "Статус счёта: " + (o.invoice_status || "неизвестен");
  };

  return (
    <section className="panel" aria-labelledby="commercial-orders-heading">
      <div className="panel-title-row">
        <div>
          <p className="eyebrow">Канонический коммерческий маршрут</p>
          <h2 id="commercial-orders-heading">Заказы и платежи</h2>
        </div>
        <button type="button" className="ghost" disabled={busy || !apiKey}
          onClick={() => void refresh()}>
          {busy ? "Обновляем…" : "Обновить"}
        </button>
      </div>
      <p className="muted-text">Здесь отражаются только реальные состояния OrderStore и InvoiceRegistry.
        Счёт, подтверждённый платёж и исполнение различаются. Настоящая оплата и
        автоматическое исполнение ещё не включены.</p>
      {error ? <div className="error-box inline-error" role="alert">{error}</div> : null}
      {!loaded && !error ? <p className="muted-text">Подтверждённые данные пока не загружены.</p> : null}
      {loaded && !orders.length ? <p className="empty-state">Подтверждённых коммерческих заказов пока нет.</p> : null}
      {orders.length ? (
        <>
          <p className="muted-text">Заказов: {orders.length}. Это не количество оплаченных продаж.</p>
          <ul>
            {orders.map((o) => (
              <li key={o.order_id}>
                <button type="button" className="ghost" aria-expanded={selectedId === o.order_id}
                  onClick={() => setSelectedId((current) => current === o.order_id ? "" : o.order_id)}>
                  {money(o.amount_minor, o.currency)} · {stateText(o)}
                </button>
                {selected?.order_id === o.order_id ? (
                  <div className="recovery-box">
                    <p><strong>Заказ:</strong> {o.order_id}</p>
                    <p><strong>Счёт:</strong> {o.invoice_id}</p>
                    <p><strong>Предложение:</strong> {o.offer_id}</p>
                    <p><strong>Начислено в Billing:</strong> {money(o.paid_minor, o.currency)}</p>
                    <p>Внешнее подтверждение PSP и получение клиентом товара этим экраном не доказаны.</p>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
