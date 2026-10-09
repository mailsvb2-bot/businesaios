import { useRef, useState } from "react";

/**
 * Phase-18 bounded support console. The server, not the browser, determines
 * tenant, business and operator identity from a scoped SUPPORT credential.
 * No credential persistence, owner impersonation, or cross-business fallback.
 */
export function SupportOperatorConsole({ apiBase }) {
  const [credential, setCredential] = useState("");
  const [session, setSession] = useState(null);
  const [cases, setCases] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
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
        {error ? <p className="error-box inline-error" role="alert">{error}</p> : null}
        {notice ? <p role="status">{notice}</p> : null}
        {!cases.length ? <p className="muted-text">Для этого бизнеса обращений пока нет.</p> : (
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
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
