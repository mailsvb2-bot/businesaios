import { useEffect, useRef, useState } from "react";

/** Owner support inbox. All state comes from the authenticated canonical API. */
export function SupportCasesWorkspace({ apiBase, apiKey, getJson, postJson }) {
  const [cases, setCases] = useState([]);
  const [category, setCategory] = useState("technical");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [caseHistory, setCaseHistory] = useState(null);
  const [historyBusy, setHistoryBusy] = useState("");
  const [historyError, setHistoryError] = useState(null);
  const historyEpoch = useRef(0);
  const pending = useRef(null);
  const url = apiBase.replace(/\/$/, "") + "/business-workspace/support-cases";
  const headers = apiKey ? { "X-API-Key": apiKey } : {};

  useEffect(() => {
    let active = true;
    if (!apiKey) return () => { active = false; };
    getJson(url, headers)
      .then((payload) => { if (active) setCases(Array.isArray(payload?.cases) ? payload.cases : []); })
      .catch((reason) => { if (active) setError("Не удалось загрузить обращения: " + (reason.message || "ошибка сети")); });
    return () => { active = false; };
  }, [url, apiKey, getJson]);

  const toggleHistory = async (item) => {
    if (!apiKey || busy || historyBusy) return;
    if (caseHistory?.case_id === item.id) {
      historyEpoch.current += 1;
      setCaseHistory(null);
      setHistoryError(null);
      return;
    }
    const epoch = ++historyEpoch.current;
    setCaseHistory(null);
    setHistoryBusy(item.id);
    setHistoryError(null);
    try {
      const data = await getJson(url + "/" + encodeURIComponent(item.id) + "/history", headers);
      if (epoch !== historyEpoch.current) return;
      if (data?.case_id !== item.id || !Array.isArray(data.entries) ||
          !Number.isInteger(data.revision) || !Number.isInteger(data.total) ||
          data.total < data.entries.length) {
        throw new Error("Сервер вернул некорректную историю.");
      }
      setCaseHistory(data);
    } catch (reason) {
      if (epoch === historyEpoch.current) setHistoryError({ caseId: item.id, message: "Не удалось получить историю: " + (reason.message || "ошибка сети") });
    } finally {
      if (epoch === historyEpoch.current) setHistoryBusy("");
    }
  };

  const refresh = async () => {
    if (busy || !apiKey) return;
    setBusy("refresh");
    setError("");
    try {
      const payload = await getJson(url, headers);
      setCases(Array.isArray(payload?.cases) ? payload.cases : []);
      historyEpoch.current += 1;
      setCaseHistory(null);
      setHistoryBusy("");
      setHistoryError(null);
      setNotice("Статусы получены из защищённого журнала BusinessAIOS.");
    } catch (reason) {
      setError("Не удалось обновить обращения: " + (reason.message || "ошибка сети"));
    } finally {
      setBusy("");
    }
  };

  const create = async (event) => {
    event.preventDefault();
    if (!apiKey || busy || summary.trim().length < 3) return;
    const signature = JSON.stringify([category, summary.trim()]);
    // A retry after a lost response must reuse its idempotency key.
    if (!pending.current || pending.current.signature !== signature) {
      pending.current = { signature, key: "support-" + crypto.randomUUID() };
    }
    setBusy("create");
    setError("");
    setNotice("");
    try {
      const created = await postJson(url, {
        category, summary: summary.trim(), idempotency_key: pending.current.key
      }, headers);
      if (!created?.id || created?.status !== "open") {
        throw new Error("Создание не подтверждено сервером. Проверьте историю обращений.");
      }
      // The POST response is already a durable server receipt. A later list
      // refresh must never retroactively turn a successful create into "failed".
      pending.current = null;
      setSummary("");
      setCases((previous) => [created, ...previous.filter((item) => item.id !== created.id)]);
      setNotice("Обращение зарегистрировано. Номер: " + created.id);
      try {
        const payload = await getJson(url, headers);
        if (Array.isArray(payload?.cases)) setCases(payload.cases);
      } catch {
        // Keep the confirmed case visible. The owner can refresh status later.
        setNotice("Обращение зарегистрировано. Номер: " + created.id + ". Список можно обновить позже.");
      }
    } catch (reason) {
      setError("Не удалось подтвердить создание: " + (reason.message || "ошибка сети") + ". Повторная отправка использует тот же идентификатор операции.");
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="panel" aria-labelledby="business-support-title">
      <div className="panel-title-row">
        <div><p className="eyebrow">Помощь и обращения</p><h2 id="business-support-title">Поддержка</h2></div>
        <button type="button" className="ghost" disabled={Boolean(busy) || !apiKey} onClick={refresh}>Обновить статусы</button>
      </div>
      <p className="muted-text">Обращение привязано к вашему бизнесу. Не вставляйте в текст пароли, токены и ключи доступа.</p>
      {error ? <div className="error-box inline-error" role="alert">{error}</div> : null}
      {notice ? <p role="status">{notice}</p> : null}
      <form onSubmit={create}>
        <label>Тема
          <select value={category} disabled={Boolean(busy)} onChange={(e) => { setCategory(e.target.value); pending.current = null; }}>
            <option value="technical">Техническая проблема</option>
            <option value="integration">Интеграция</option>
            <option value="billing">Оплата</option>
            <option value="security">Безопасность</option>
            <option value="general">Общий вопрос</option>
          </select>
        </label>
        <label>Что произошло?
          <textarea value={summary} maxLength={1000} rows={3} disabled={Boolean(busy)}
            onChange={(e) => { setSummary(e.target.value); pending.current = null; }}
            placeholder="Опишите проблему без конфиденциальных данных" />
        </label>
        <button type="submit" className="primary" disabled={!apiKey || Boolean(busy) || summary.trim().length < 3}>
          {busy === "create" ? "Отправляем…" : "Создать обращение"}
        </button>
      </form>
      <h3>Мои обращения</h3>
      {cases.length === 0 ? <p className="muted-text">Обращений пока нет. После отправки здесь появится подтверждённый статус.</p> : (
        <ul>
          {cases.map((item) => (
            <li key={item.id}>
              <strong>{item.category} · {item.status === "open" ? "Открыто" : item.status === "claimed" ? "В работе" : item.status === "resolved" ? "Решено" : "Статус неизвестен"}</strong>
              <p>{item.summary}</p>
              <small>{item.id} · Изменено: {item.updated_at}</small>
              <div>
                <button type="button" className="ghost"
                  disabled={Boolean(busy) || Boolean(historyBusy)}
                  onClick={() => toggleHistory(item)}>
                  {historyBusy === item.id ? "Загружаем историю…" :
                    caseHistory?.case_id === item.id ? "Скрыть историю" : "Показать историю"}
                </button>
                {historyError?.caseId === item.id && !historyBusy ? <p role="alert">{historyError.message}</p> : null}
                {caseHistory?.case_id === item.id ? (
                  <div aria-label={"История обращения " + item.id}>
                    <p className="muted-text">Подтверждено событий: {caseHistory.total}
                      {caseHistory.truncated ? " · Показаны последние " + caseHistory.entries.length : ""}
                    </p>
                    <ol>
                      {caseHistory.entries.map((event) => (
                        <li key={event.revision}>
                          {event.action === "created" ? "Создано" :
                            event.action === "claimed" ? "Взято в работу" :
                            event.action === "released" ? "Возвращено в очередь" :
                            event.action === "resolved" ? "Решено" : "Действие неизвестно"}
                          {" · "}{event.occurred_at}
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
