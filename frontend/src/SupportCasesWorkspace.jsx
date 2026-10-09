import { useEffect, useRef, useState } from "react";

/** Owner support inbox. All state comes from the authenticated canonical API. */
export function SupportCasesWorkspace({ apiBase, apiKey, getJson, postJson }) {
  const [cases, setCases] = useState([]);
  const [category, setCategory] = useState("technical");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
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

  const refresh = async () => {
    if (busy || !apiKey) return;
    setBusy("refresh");
    setError("");
    try {
      const payload = await getJson(url, headers);
      setCases(Array.isArray(payload?.cases) ? payload.cases : []);
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
      pending.current = null;
      setSummary("");
      const payload = await getJson(url, headers);
      setCases(Array.isArray(payload?.cases) ? payload.cases : [created]);
      setNotice("Обращение зарегистрировано. Номер: " + created.id);
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
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
