import { useRef, useState } from "react";

/**
 * Phase-18 bounded support console. The server, not the browser, determines
 * tenant, business and operator identity from a scoped SUPPORT credential.
 * No credential persistence, owner impersonation, or cross-business fallback.
 */
function SupportCaseHistory({ history }) {
  return (
    <div aria-label={"История обращения " + history.case_id}>
      <p className="muted-text">Подтверждено событий: {history.total}
        {history.truncated ? " · Показаны последние " + history.entries.length : ""}
      </p>
      <ol>
        {history.entries.map((entry) => (
          <li key={entry.revision}>
            {entry.action === "created" ? "Создано" :
              entry.action === "claimed" ? "Взято в работу" :
                entry.action === "released" ? "Возвращено в очередь" : "Решено"}
            {" · "}{entry.occurred_at}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function SupportOperatorConsole({ apiBase }) {
  const [credential, setCredential] = useState("");
  const [session, setSession] = useState(null);
  const [cases, setCases] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [history, setHistory] = useState(null);
  const [lookupId, setLookupId] = useState("");
  const [historyBusy, setHistoryBusy] = useState("");
  const [historyError, setHistoryError] = useState(null);
  const historyEpoch = useRef(0);
  const pending = useRef(null);
  const epoch = useRef(0);
  const base = apiBase.replace(/\/$/, "") + "/platform-support";

  const request = async (key, path, payload) => {
    const response = await fetch(base + path, {
      method: payload ? "POST" : "GET",
      headers: { "X-API-Key": key, ...(payload ? { "Content-Type": "application/json" } : {}) },
      ...(payload ? { body: JSON.stringify(payload) } : {}),
      credentials: "omit",
      cache: "no-store"
    });
    const text = await response.text();
    let result = {};
    try { result = text ? JSON.parse(text) : {}; } catch { /* Invalid response is never treated as success. */ }
    if (!response.ok) {
      const failure = new Error(typeof result.detail === "string" ? result.detail : "HTTP " + response.status);
      failure.httpStatus = response.status;
      throw failure;
    }
    return result;
  };

  const logout = () => {
    epoch.current += 1;
    historyEpoch.current += 1;
    setHistory(null);
    setLookupId("");
    setHistoryBusy("");
    setHistoryError(null);
    pending.current = null;
    setCredential("");
    setSession(null);
    setCases([]);
    setBusy("");
    setError("");
    setNotice("");
  };

  const authenticate = async (event) => {
    event.preventDefault();
    const key = credential.trim();
    if (!key || busy) return;
    const generation = ++epoch.current;
    setBusy("login");
    setError("");
    setNotice("");
    try {
      const identity = await request(key, "/session");
      if (!identity.can_manage_cases || !identity.tenant_id || !identity.business_id || !identity.operator_id) {
        throw new Error("Сервер не подтвердил полномочия оператора.");
      }
      const queue = await request(key, "/cases");
      if (generation !== epoch.current) return;
      if (!Array.isArray(queue.cases)) throw new Error("Некорректный ответ очереди.");
      setCases(queue.cases);
      setSession({ key, identity });
      setCredential("");
      setNotice("Доступ подтверждён для бизнеса " + identity.business_id + ".");
    } catch (reason) {
      if (generation === epoch.current) setError("Не удалось открыть очередь: " + reason.message);
    } finally {
      if (generation === epoch.current) setBusy("");
    }
  };

  const refresh = async () => {
    if (!session || busy) return;
    const generation = epoch.current;
    historyEpoch.current += 1;
    setHistory(null);
    setHistoryBusy("");
    setHistoryError(null);
    setBusy("refresh");
    setError("");
    try {
      const queue = await request(session.key, "/cases");
      if (generation !== epoch.current) return;
      if (!Array.isArray(queue.cases)) throw new Error("Некорректный ответ очереди.");
      setCases(queue.cases);
      setNotice("Очередь обновлена из BusinessAIOS.");
    } catch (reason) {
      if (generation !== epoch.current) return;
      if (reason.httpStatus === 401 || reason.httpStatus === 403) {
        logout();
        setError("Срок доступа истёк или права отозваны. Войдите повторно.");
      } else {
        setError("Не удалось обновить очередь; показаны прежние данные: " + reason.message);
      }
    } finally {
      if (generation === epoch.current) setBusy("");
    }
  };

  const toggleHistory = async (item) => {
    if (!session || busy || historyBusy) return;
    if (history?.case_id === item.id) {
      historyEpoch.current += 1;
      setHistory(null);
      setHistoryError(null);
      return;
    }
    const generation = epoch.current;
    const requestEpoch = ++historyEpoch.current;
    setHistory(null);
    setHistoryBusy(item.id);
    setHistoryError(null);
    try {
      const result = await request(session.key, "/cases/" + encodeURIComponent(item.id) + "/history");
      if (generation !== epoch.current || requestEpoch !== historyEpoch.current) return;
      if (result?.case_id !== item.id || !Array.isArray(result.entries) ||
          !Number.isInteger(result.revision) || result.revision < item.revision ||
          !Number.isInteger(result.total) || result.total < result.entries.length ||
          result.entries.some((entry) => !Number.isInteger(entry.revision) ||
            !["created", "claimed", "released", "resolved"].includes(entry.action) ||
            typeof entry.occurred_at !== "string")) {
        throw new Error("Сервер вернул некорректную историю обращения.");
      }
      setHistory(result);
    } catch (reason) {
      if (generation !== epoch.current || requestEpoch !== historyEpoch.current) return;
      if (reason.httpStatus === 401 || reason.httpStatus === 403) {
        logout();
        setError("Доступ оператора отозван. Повторите вход.");
      } else {
        setHistoryError({ caseId: item.id, message: "Не удалось получить историю: " + reason.message });
      }
    } finally {
      if (generation === epoch.current && requestEpoch === historyEpoch.current) setHistoryBusy("");
    }
  };

  const searchHistory = async (event) => {
    event.preventDefault();
    if (!session || busy || historyBusy) return;
    const id = lookupId.trim().toLowerCase();
    if (!/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(id)) {
      historyEpoch.current += 1;
      setHistory(null);
      setHistoryError({ caseId: id, message: "Введите корректный номер обращения (UUID)." });
      return;
    }
    if (history?.case_id === id) return;
    await toggleHistory({ id, revision: 0 });
  };

  const transition = async (item, action) => {
    if (!session || busy) return;
    const generation = epoch.current;
    const signature = [item.id, item.revision, action].join(":");
    // The exact same operation after a lost HTTP response must keep its key.
    if (!pending.current || pending.current.signature !== signature) {
      pending.current = { signature, key: "support-op-" + crypto.randomUUID() };
    }
    setBusy(signature);
    setError("");
    setNotice("");
    try {
      const result = await request(session.key,
        "/cases/" + encodeURIComponent(item.id) + "/" + action,
        { expected_revision: item.revision, idempotency_key: pending.current.key });
      if (generation !== epoch.current) return;
      if (result.id !== item.id || !Number.isInteger(result.revision) || result.revision <= item.revision) {
        throw new Error("Сервер не подтвердил изменение. Повтор использует прежний ключ.");
      }
      pending.current = null;
      historyEpoch.current += 1;
      setHistory(null);
      setHistoryBusy("");
      setHistoryError(null);
      setCases((existing) => existing.map((row) => row.id === result.id ? result : row));
      setNotice("Изменение подтверждено сервером. Обращение " + result.id + ".");
      try {
        const queue = await request(session.key, "/cases");
        if (generation === epoch.current && Array.isArray(queue.cases)) setCases(queue.cases);
      } catch {
        if (generation === epoch.current) setNotice("Операция подтверждена. Общую очередь можно обновить позже.");
      }
    } catch (reason) {
      if (generation !== epoch.current) return;
      if (reason.httpStatus === 401 || reason.httpStatus === 403) {
        logout();
        setError("Доступ оператора отозван. Повторите вход.");
      } else if (reason.httpStatus === 409) {
        // The client must not blindly retry a stale revision.
        pending.current = null;
        setError("Конфликт состояния. Обновите очередь перед новым действием: " + reason.message);
      } else {
        setError("Статус операции неизвестен: " + reason.message + ". Повтор того же действия сохранит прежний ключ.");
      }
    } finally {
      if (generation === epoch.current) setBusy("");
    }
  };

  if (!session) {
    return (
      <main className="onboarding-shell">
        <section className="panel" aria-labelledby="support-console-title">
          <p className="eyebrow">BusinessAIOS · оператор</p>
          <h1 id="support-console-title">Очередь обращений</h1>
          <p className="muted-text">Нужен отдельный выданный администратором ключ роли SUPPORT с правом support_case_manage, привязанный к одному бизнесу. Ключ владельца не подходит.</p>
          {error ? <p className="error-box inline-error" role="alert">{error}</p> : null}
          <form onSubmit={authenticate}>
            <label>Ключ доступа оператора
              <input type="password" autoComplete="off" spellCheck={false} value={credential}
                onChange={(event) => setCredential(event.target.value)} />
            </label>
            <button className="primary" type="submit" disabled={!credential.trim() || Boolean(busy)}>
              {busy ? "Проверяем доступ…" : "Войти в поддержку"}
            </button>
          </form>
          <p className="muted-text">Ключ остаётся только в памяти открытой вкладки. После обновления страницы потребуется новый вход.</p>
        </section>
      </main>
    );
  }

  const operatorId = session.identity.operator_id;
  return (
    <main className="onboarding-shell">
      <section className="panel" aria-labelledby="support-console-title">
        <div className="panel-title-row">
          <div>
            <p className="eyebrow">BusinessAIOS · поддержка</p>
            <h1 id="support-console-title">Очередь обращений</h1>
            <p className="muted-text">Бизнес: {session.identity.business_id} · Оператор: {operatorId}</p>
          </div>
          <button type="button" className="ghost" onClick={logout}>Выйти</button>
        </div>
        <button type="button" className="ghost" onClick={refresh} disabled={Boolean(busy)}>Обновить очередь</button>
        <form onSubmit={searchHistory} aria-label="Поиск истории обращения">
          <label>Номер обращения
            <input type="text" autoComplete="off" spellCheck={false}
              placeholder="UUID обращения" value={lookupId}
              disabled={Boolean(busy) || Boolean(historyBusy)}
              onChange={(event) => {
                setLookupId(event.target.value);
                setHistoryError(null);
              }} />
          </label>
          <button type="submit" className="ghost" disabled={Boolean(busy) || Boolean(historyBusy) || !lookupId.trim()}>
            {historyBusy && historyBusy === lookupId.trim().toLowerCase() ? "Ищем историю…" : "Найти историю"}
          </button>
        </form>
        {historyError?.caseId === lookupId.trim().toLowerCase() ? <p role="alert">{historyError.message}</p> : null}
        {history && !cases.some((item) => item.id === history.case_id) ? (
          <section aria-label="Результат поиска истории">
            <p>Обращение {history.case_id} · Версия: {history.revision}</p>
            <SupportCaseHistory history={history} />
          </section>
        ) : null}
        {error ? <p className="error-box inline-error" role="alert">{error}</p> : null}
        {notice ? <p role="status">{notice}</p> : null}
        {!cases.length ? <p className="muted-text">В очереди нет открытых обращений.</p> : (
          <ul>
            {cases.map((item) => {
              const mine = item.status === "claimed" && item.claimed_by_operator_user_id === operatorId;
              return (
                <li key={item.id}>
                  <strong>{item.category} · {item.status === "open" ? "Открыто" : item.status === "claimed" ? "В работе" : "Решено"}</strong>
                  <p>{item.summary}</p>
                  <small>{item.id} · Версия: {item.revision} · {item.updated_at}</small>
                  {item.status === "claimed" && !mine ? <p className="muted-text">Взято другим оператором.</p> : null}
                  <div className="panel-title-row">
                    {item.status === "open" ? (
                      <button type="button" className="primary" disabled={Boolean(busy)}
                        onClick={() => transition(item, "claim")}>Взять в работу</button>
                    ) : null}
                    {mine ? (
                      <>
                        <button type="button" className="ghost" disabled={Boolean(busy)}
                          onClick={() => transition(item, "release")}>Освободить</button>
                        <button type="button" className="primary" disabled={Boolean(busy)}
                          onClick={() => transition(item, "resolve")}>Закрыть обращение</button>
                      </>
                    ) : null}
                  </div>
                  <button type="button" className="ghost"
                    disabled={Boolean(busy) || Boolean(historyBusy)}
                    onClick={() => toggleHistory(item)}>
                    {historyBusy === item.id ? "Загружаем историю…" :
                      history?.case_id === item.id ? "Скрыть историю" : "Показать историю"}
                  </button>
                  {historyError?.caseId === item.id ? <p role="alert">{historyError.message}</p> : null}
                  {history?.case_id === item.id ? <SupportCaseHistory history={history} /> : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
