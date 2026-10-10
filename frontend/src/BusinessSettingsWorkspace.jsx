import { useEffect, useRef, useState } from "react";

const TIMEZONES = [
  ["Europe/Moscow", "Москва"], ["Europe/Kaliningrad", "Калининград"],
  ["Europe/Samara", "Самара"], ["Asia/Yekaterinburg", "Екатеринбург"],
  ["Asia/Omsk", "Омск"], ["Asia/Novosibirsk", "Новосибирск"],
  ["Asia/Krasnoyarsk", "Красноярск"], ["Asia/Irkutsk", "Иркутск"],
  ["Asia/Yakutsk", "Якутск"], ["Asia/Vladivostok", "Владивосток"],
  ["Europe/Berlin", "Берлин"], ["Europe/London", "Лондон"],
  ["Asia/Dubai", "Дубай"], ["Asia/Tbilisi", "Тбилиси"],
  ["UTC", "UTC"],
];

export function BusinessSettingsWorkspace({ apiBase, apiKey, getJson, postJson, onSaved }) {
  const [settings, setSettings] = useState(null);
  const [name, setName] = useState("");
  const [activity, setActivity] = useState("");
  const [timezone, setTimezone] = useState("Europe/Moscow");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef(null);
  const generation = useRef(0);
  const url = apiBase.replace(/\/$/, "") + "/business-workspace/settings";
  const headers = apiKey ? { "X-API-Key": apiKey } : {};

  const apply = (value) => {
    if (!value || !Number.isInteger(value.revision) || !value.business_id) {
      throw new Error("Некорректное подтверждение сервера");
    }
    setSettings(value);
    setName(value.business_name || "");
    setActivity(value.activity_description || "");
    setTimezone(value.timezone_name || "Europe/Moscow");
  };

  useEffect(() => {
    const seq = ++generation.current;
    if (!apiKey) return;
    getJson(url, headers).then((result) => {
      if (seq === generation.current) apply(result);
    }).catch((reason) => {
      if (seq === generation.current) setError("Не удалось загрузить настройки: " + reason.message);
    });
    return () => { generation.current += 1; };
  }, [url, apiKey, getJson]);

  const refresh = async () => {
    if (!apiKey || busy) return;
    const seq = ++generation.current;
    setBusy("refresh");
    setError("");
    try {
      const result = await getJson(url, headers);
      if (seq !== generation.current) return;
      apply(result);
      pending.current = null;
      setNotice("Настройки получены из кабинета бизнеса.");
    } catch (reason) {
      if (seq === generation.current) setError("Не удалось обновить настройки: " + reason.message);
    } finally {
      if (seq === generation.current) setBusy("");
    }
  };

  const save = async (event) => {
    event.preventDefault();
    if (!apiKey || busy || !settings || !name.trim()) return;
    const payload = {
      business_name: name.trim(), activity_description: activity.trim(),
      timezone_name: timezone, expected_revision: settings.revision,
    };
    const signature = JSON.stringify(payload);
    if (!pending.current || pending.current.signature !== signature) {
      pending.current = { signature, key: "settings-" + crypto.randomUUID() };
    }
    const seq = generation.current;
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const result = await postJson(url, payload, {
        ...headers, "X-Idempotency-Key": pending.current.key,
      });
      if (seq !== generation.current) return;
      if (result.business_id !== settings.business_id ||
          !Number.isInteger(result.revision) || result.revision <= settings.revision) {
        throw new Error("Сервер не подтвердил изменение версии");
      }
      apply(result);
      pending.current = null;
      onSaved?.(result);
      setNotice("Настройки сохранены.");
    } catch (reason) {
      if (seq !== generation.current) return;
      if (reason.httpStatus === 409) {
        pending.current = null;
        setError("Настройки изменились в другой вкладке. Обновите данные перед сохранением.");
      } else {
        setError("Результат сохранения неизвестен: " + reason.message + ". Повтор использует тот же ключ операции.");
      }
    } finally {
      if (seq === generation.current) setBusy("");
    }
  };

  const zoneOptions = [...TIMEZONES];
  const knownZones = new Set(zoneOptions.map(([id]) => id));
  // The donor cockpit allowed every IANA zone, not only the short Russian list.
  const allZones = typeof Intl.supportedValuesOf === "function"
    ? Intl.supportedValuesOf("timeZone") : [];
  for (const zone of allZones) {
    if (!knownZones.has(zone)) {
      zoneOptions.push([zone, zone.replaceAll("_", " ")]);
      knownZones.add(zone);
    }
  }
  if (timezone && !knownZones.has(timezone)) zoneOptions.push([timezone, timezone]);

  return (
    <section className="panel" aria-labelledby="business-settings-title">
      <div className="panel-title-row">
        <div><p className="eyebrow">Профиль бизнеса</p><h2 id="business-settings-title">Настройки</h2></div>
        <button type="button" className="ghost" onClick={refresh} disabled={!apiKey || Boolean(busy)}>Обновить</button>
      </div>
      <p className="muted-text">Данные относятся только к текущему бизнесу. Изменения подтверждаются сервером.</p>
      {error ? <p role="alert" className="error-box inline-error">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      {!settings ? <p className="muted-text">Загружаем настройки…</p> : (
        <form onSubmit={save}>
          <label>Название бизнеса
            <input value={name} maxLength={200} disabled={Boolean(busy)}
              onChange={(event) => { setName(event.target.value); pending.current = null; }} required />
          </label>
          <label>Описание деятельности
            <textarea value={activity} maxLength={2000} rows={3} disabled={Boolean(busy)}
              onChange={(event) => { setActivity(event.target.value); pending.current = null; }} />
          </label>
          <label>Часовой пояс
            <select value={timezone} disabled={Boolean(busy)} onChange={(event) => { setTimezone(event.target.value); pending.current = null; }}>
              {zoneOptions.map(([id, title]) => <option value={id} key={id}>{title}</option>)}
            </select>
          </label>
          <button type="submit" className="primary" disabled={!apiKey || Boolean(busy) || !name.trim()}>
            {busy === "save" ? "Сохраняем…" : "Сохранить настройки"}
          </button>
        </form>
      )}
    </section>
  );
}
