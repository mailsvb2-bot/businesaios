import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const commercialPath = "/business-workspace/commercial";
const headersFor = (key) => ({ "X-API-Key": key });
const receiptIsOrder = (order) => Boolean(
  order && typeof order.order_id === "string" && order.order_id &&
  typeof order.invoice_id === "string" && order.invoice_id &&
  Number.isSafeInteger(order.amount_minor) && order.amount_minor > 0 &&
  Number.isSafeInteger(order.paid_minor) && order.paid_minor >= 0 &&
  order.paid_minor <= order.amount_minor && typeof order.currency === "string" && order.currency
);
const isSafeCheckoutUrl = (url) => {
  if (typeof url !== "string" || url.length > 4096 || /[\x00-\x1f]/.test(url)) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && Boolean(parsed.hostname) &&
      !parsed.username && !parsed.password && !parsed.hash;
  } catch {
    return false;
  }
};

/** Owner-side read/write journey; every money and delivery statement comes from canonical server owners. */
export function CommercialSalesWorkspace({
  apiBase, apiKey, tenantId, businessId, getJson, postJson
}) {
  const endpoint = apiBase.replace(/\/$/, "") + commercialPath;
  const auth = useMemo(() => headersFor(apiKey), [apiKey]);
  const [orders, setOrders] = useState([]);
  const [leads, setLeads] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [selectedLead, setSelectedLead] = useState("");
  const [selectedProgram, setSelectedProgram] = useState("");
  const [selectedOffer, setSelectedOffer] = useState("");
  const [offers, setOffers] = useState([]);
  const [quoteBusy, setQuoteBusy] = useState(false);
  const [checkoutLinks, setCheckoutLinks] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [focusedLead, setFocusedLead] = useState("");
  const [leadContext, setLeadContext] = useState(null);
  const [leadContextError, setLeadContextError] = useState("");
  // Reuse the same key after an ambiguous network failure. No blind second order.
  const pendingRequest = useRef(null);

  const refresh = useCallback(async (signal) => {
    if (!apiKey) return;
    setBusy(true);
    setError("");
    try {
      const [data, leadResponse, programResponse] = await Promise.all([
        getJson(endpoint + "/orders", auth),
        getJson(endpoint + "/leads", auth),
        getJson(apiBase.replace(/\/$/, "") + "/business-workspace/programs", auth),
      ]);
      if (signal?.aborted) return;
      if (!Array.isArray(data?.orders) || !data.orders.every(receiptIsOrder)) {
        throw new Error("Сервер вернул непроверенные суммы или счета");
      }
      if (!Array.isArray(leadResponse?.leads) ||
          leadResponse.leads.some((lead) => !lead.lead_id || !lead.customer_id ||
            !lead.conversation_id || !lead.channel)) {
        throw new Error("Некорректная история обращений");
      }
      if (!Array.isArray(programResponse?.programs)) {
        throw new Error("Каталог программ недоступен");
      }
      setOrders(data.orders);
      setLeads(leadResponse.leads);
      setPrograms(programResponse.programs.filter((item) =>
        item?.id && item.status === "active" && item.access_mode === "paid"));
      setLoaded(true);
    } catch (reason) {
      if (!signal?.aborted) {
        setError("Не удалось прочитать канонические данные: " +
          (reason?.message || "ошибка сети") + ". Повторите чтение перед новым действием.");
        setLoaded(false);
      }
    } finally {
      if (!signal?.aborted) setBusy(false);
    }
  }, [apiBase, apiKey, auth, endpoint, getJson]);

  useEffect(() => {
    const controller = new AbortController();
    setOrders([]);
    setLeads([]);
    setPrograms([]);
    setSelectedLead("");
    setSelectedProgram("");
    setSelectedOffer("");
    setOffers([]);
    setSelectedId("");
    setCheckoutLinks({});
    setFocusedLead("");
    setLeadContext(null);
    setLeadContextError("");
    setLoaded(false);
    pendingRequest.current = null;
    if (apiKey) void refresh(controller.signal);
    return () => controller.abort();
  }, [apiKey, refresh]);

  useEffect(() => {
    let active = true;
    setOffers([]);
    setSelectedOffer("");
    if (!selectedProgram || !apiKey) return () => { active = false; };
    setQuoteBusy(true);
    getJson(endpoint + "/offers/" + encodeURIComponent(selectedProgram), auth)
      .then((result) => {
        if (!active) return;
        if (result?.program_id !== selectedProgram || !Array.isArray(result.offers) ||
            result.offers.some((offer) => !offer.offer_id ||
              !Number.isSafeInteger(offer.amount_minor) || offer.amount_minor <= 0 ||
              !offer.currency || !offer.fingerprint)) {
          throw new Error("Каталог не подтвердил стоимость предложений");
        }
        setOffers(result.offers);
      })
      .catch((reason) => {
        if (active) setError("Не удалось получить серверные цены: " +
          (reason?.message || "ошибка каталога"));
      })
      .finally(() => { if (active) setQuoteBusy(false); });
    return () => { active = false; };
  }, [apiKey, auth, endpoint, getJson, selectedProgram]);

  const liveLead = leads.find((lead) =>
    lead.lead_id === selectedLead && lead.lifecycle_status === "active");
  const quote = offers.find((item) => item.offer_id === selectedOffer);
  const money = (minor, currency) => (minor / 100).toLocaleString("ru-RU", {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }) + " " + currency;
  const selected = useMemo(
    () => orders.find((item) => item.order_id === selectedId) || null,
    [orders, selectedId]
  );
  const stateText = (o) => {
    if (o.status === "cancelled") return "Отменён";
    if (o.status === "fulfilled") return "Отмечен исполненным";
    if (o.invoice_status === "credited") return "Кредитован или возвращён";
    if (o.invoice_status === "paid") return o.provider_verified === true
      ? "Платёж подтверждён PSP" : "Оплачен в Billing (PSP ещё не сверена)";
    if (o.invoice_status === "partially_paid") return "Частично оплачен";
    if (o.invoice_status === "issued") return "Счёт выставлен, оплата не подтверждена";
    return "Статус счёта: " + (o.invoice_status || "неизвестен");
  };

  const showLeadContext = async (leadId) => {
    if (leadId === focusedLead) {
      setFocusedLead("");
      setLeadContext(null);
      setLeadContextError("");
      return;
    }
    setFocusedLead(leadId);
    setLeadContext(null);
    setLeadContextError("");
    try {
      const data = await getJson(endpoint + "/leads/" + encodeURIComponent(leadId) + "/context", auth);
      if (data?.lead_id !== leadId || !data?.context_fingerprint ||
          !Array.isArray(data?.orders) || !Number.isSafeInteger(data?.inbound_message_count)) {
        throw new Error("Сервер не подтвердил контекст обращения");
      }
      setLeadContext(data);
    } catch (reason) {
      setLeadContextError("Контекст недоступен: " + (reason?.message || "ошибка сервера"));
    }
  };

  const createOrder = async (event) => {
    event.preventDefault();
    if (!loaded || busy || !apiKey || !liveLead || !quote || !selectedProgram) return;
    const combination = [tenantId, businessId, liveLead.lead_id,
      liveLead.customer_id, selectedProgram, quote.offer_id].join(":");
    if (pendingRequest.current?.combination !== combination) {
      pendingRequest.current = { combination, key: crypto.randomUUID() };
    }
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const response = await postJson(endpoint + "/orders", {
        lead_id: liveLead.lead_id, customer_id: liveLead.customer_id,
        program_id: selectedProgram, offer_id: quote.offer_id,
        idempotency_key: pendingRequest.current.key,
      }, auth);
      if (!receiptIsOrder(response) || response.amount_minor !== quote.amount_minor ||
          response.currency !== quote.currency || response.program_id !== selectedProgram ||
          response.lead_id !== liveLead.lead_id ||
          response.customer_id !== liveLead.customer_id ||
          response.offer_id !== quote.offer_id) {
        throw new Error("Создание счёта не совпало с подтверждённым предложением");
      }
      const persisted = await getJson(endpoint + "/orders/" +
        encodeURIComponent(response.order_id), auth);
      if (!receiptIsOrder(persisted) || persisted.invoice_id !== response.invoice_id ||
          persisted.amount_minor !== response.amount_minor ||
          persisted.currency !== response.currency) {
        throw new Error("Запись счёта не подтверждена повторным чтением");
      }
      pendingRequest.current = null;
      setSelectedId(persisted.order_id);
      setNotice("Заказ и счёт сохранены в BusinessAIOS. Оплата ещё не подтверждена.");
      await refresh();
    } catch (reason) {
      setError("Создание счёта не завершено: " + (reason?.message || "ошибка сети") +
        ". Обновите список; повторная отправка использует прежний ключ операции.");
    } finally {
      setBusy(false);
    }
  };

  const startCheckout = async (order) => {
    if (!apiKey || busy || !receiptIsOrder(order) ||
        order.invoice_status !== "issued" || order.paid_minor !== 0) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const session = await postJson(endpoint + "/orders/" +
        encodeURIComponent(order.order_id) + "/checkout", {}, auth);
      if (session?.order_id !== order.order_id || session?.invoice_id !== order.invoice_id ||
          session?.tenant_id !== tenantId || session?.business_id !== businessId ||
          session?.amount_minor !== order.amount_minor || session?.currency !== order.currency ||
          session?.status !== "awaiting_payment" || !session?.external_reference ||
          !isSafeCheckoutUrl(session.checkout_url)) {
        throw new Error("PSP не подтвердил безопасную ссылку и привязку платежа");
      }
      setCheckoutLinks((old) => ({ ...old, [order.order_id]: session.checkout_url }));
      setNotice("Ссылка получена от PSP. Переход к оплате не означает поступление денег.");
    } catch (reason) {
      setError("Checkout недоступен или не подтверждён: " + (reason?.message || "ошибка сервера") +
        ". Никакой платёж не отмечен полученным.");
    } finally {
      setBusy(false);
    }
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
      <p className="muted-text">Клиент и программа берутся только из канонических владельцев.
        Цена поступает из серверного каталога. Создание счёта и переход к PSP не являются
        подтверждением платежа, прав на обучение или доставки.</p>
      {error ? <div className="error-box inline-error" role="alert">{error}</div> : null}
      {notice ? <p role="status">{notice}</p> : null}
      {!loaded && !error ? <p className="muted-text">Подтверждённые данные загружаются.</p> : null}
      {loaded ? (
        <form onSubmit={createOrder} aria-label="Подготовить заказ по обращению">
          <h3>Подготовить платное предложение</h3>
          <label>Обращение клиента
            <select value={selectedLead} onChange={(event) => {
              setSelectedLead(event.target.value);
              pendingRequest.current = null;
            }}>
              <option value="">Выберите реальное обращение</option>
              {leads.filter((lead) => lead.lifecycle_status === "active").map((lead) => (
                <option key={lead.lead_id} value={lead.lead_id}>
                  {lead.channel} · {lead.customer_id} · {lead.sales_stage || "новый"}
                </option>
              ))}
            </select>
          </label>
          <label>Опубликованная платная программа
            <select value={selectedProgram} onChange={(event) => {
              setSelectedProgram(event.target.value);
              pendingRequest.current = null;
            }}>
              <option value="">Выберите программу</option>
              {programs.map((program) => (
                <option key={program.id} value={program.id}>{program.title}</option>
              ))}
            </select>
          </label>
          <label>Предложение с проверенной серверной ценой
            <select value={selectedOffer} disabled={!selectedProgram || quoteBusy}
              onChange={(event) => {
                setSelectedOffer(event.target.value);
                pendingRequest.current = null;
              }}>
              <option value="">{quoteBusy ? "Получаем цены…" : "Выберите предложение"}</option>
              {offers.map((offer) => (
                <option key={offer.offer_id} value={offer.offer_id}>
                  {offer.offer_id} · {money(offer.amount_minor, offer.currency)}
                </option>
              ))}
            </select>
          </label>
          {quote ? <p>Цена в каталоге: <strong>{money(quote.amount_minor, quote.currency)}</strong></p> : null}
          {!leads.some((lead) => lead.lifecycle_status === "active") ?
            <p className="muted-text">Нет действующих обращений: сначала нужен настоящий входящий диалог.</p> : null}
          {!programs.length ?
            <p className="muted-text">Нет опубликованных платных программ.</p> : null}
          {selectedProgram && !quoteBusy && !offers.length ?
            <p className="muted-text">Для программы не найдено ни одного разрешённого предложения.</p> : null}
          <button type="submit" disabled={busy || quoteBusy || !liveLead || !quote}>
            {busy ? "Сохраняем…" : "Создать заказ и счёт"}
          </button>
        </form>
      ) : null}
      {loaded && !leads.length ? (
        <p className="empty-state">Связанных с реальными диалогами лидов пока нет.</p>
      ) : null}
      {leads.length ? (
        <>
          <h3>Обращения и этапы продаж</h3>
          <ul>{leads.map((lead) => (
            <li key={lead.lead_id}>
              <button type="button" className="ghost"
                aria-expanded={focusedLead === lead.lead_id}
                onClick={() => void showLeadContext(lead.lead_id)}>
                {lead.channel} · {lead.sales_stage || "этап не определён"} ·
                {" "}{lead.lifecycle_status === "archived" ? "закрыт" : "активен"}
              </button>
              <small> Клиент: {lead.customer_id} · Диалог: {lead.conversation_id}</small>
              {focusedLead === lead.lead_id && leadContextError ? (
                <div className="error-box inline-error" role="alert">{leadContextError}</div>
              ) : null}
              {focusedLead === lead.lead_id && leadContext?.lead_id === lead.lead_id ? (
                <div className="recovery-box">
                  <p>Сообщений в канонической истории: {leadContext.inbound_message_count}</p>
                  <p>Актуальный этап: {leadContext.sales_stage}</p>
                  <p>Связанных заказов: {leadContext.orders.length}</p>
                  <p>{leadContext.lead_active && leadContext.customer_active &&
                      leadContext.conversation_open ?
                    "История актуальна для предложения; внешнее действие требует Policy и Execution." :
                    "Клиент, лид или диалог закрыт. Предложение заблокировано."}</p>
                </div>
              ) : null}
            </li>
          ))}</ul>
        </>
      ) : null}
      {loaded && !orders.length ?
        <p className="empty-state">Подтверждённых коммерческих заказов пока нет.</p> : null}
      {orders.length ? (
        <>
          <h3>Сохранённые заказы</h3>
          <p className="muted-text">Заказов: {orders.length}. Это не количество оплаченных продаж.</p>
          <ul>{orders.map((order) => (
            <li key={order.order_id}>
              <button type="button" className="ghost"
                aria-expanded={selectedId === order.order_id}
                onClick={() => setSelectedId((current) =>
                  current === order.order_id ? "" : order.order_id)}>
                {money(order.amount_minor, order.currency)} · {stateText(order)}
              </button>
              {selected?.order_id === order.order_id ? (
                <div className="recovery-box">
                  <p><strong>Заказ:</strong> {order.order_id}</p>
                  <p><strong>Счёт:</strong> {order.invoice_id}</p>
                  <p><strong>Предложение:</strong> {order.offer_id}</p>
                  <p><strong>Учтено в Billing:</strong> {money(order.paid_minor, order.currency)}</p>
                  {order.invoice_status === "issued" && order.paid_minor === 0 ? (
                    <button type="button" className="ghost" disabled={busy}
                      onClick={() => void startCheckout(order)}>Получить ссылку PSP</button>
                  ) : null}
                  {checkoutLinks[order.order_id] ? (
                    <p><a href={checkoutLinks[order.order_id]} target="_blank"
                      rel="noopener noreferrer">Перейти к защищённой оплате</a></p>
                  ) : null}
                  <p>Пока сервер не подтвердил PSP и исполнение, продажа не считается завершённой.</p>
                </div>
              ) : null}
            </li>
          ))}</ul>
        </>
      ) : null}
    </section>
  );
}
