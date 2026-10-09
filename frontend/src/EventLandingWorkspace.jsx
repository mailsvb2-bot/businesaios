import { useRef, useState } from "react";
import { EventLandingPreview } from "./PublicEventLanding.jsx";
import "./EventLandingWorkspace.css";

const START_CONTENT = {
  eyebrow: "Онлайн-мероприятие",
  hero_title: "",
  hero_subtitle: "",
  audience_title: "Для кого",
  audience_points: "",
  outcomes_title: "Что вы узнаете",
  outcome_points: "",
  agenda_title: "Программа",
  agenda_points: "",
  speaker_title: "Организатор",
  speaker_text: "",
  faq_title: "Частые вопросы",
  faq: [],
  cta_title: "Участие в мероприятии",
  cta_text: "",
  theme: "calm"
};

const EDITOR_FIELDS = [
  ["eyebrow", "Надзаголовок", 120, false],
  ["hero_title", "Название мероприятия", 180, true],
  ["hero_subtitle", "Описание", 800, false],
  ["audience_title", "Заголовок: для кого", 120, true],
  ["audience_points", "Кому полезно (один пункт на строку, максимум 6)", 280, false],
  ["outcomes_title", "Заголовок: результаты", 120, true],
  ["outcome_points", "Ожидаемые результаты (по одному на строку, максимум 6)", 280, false],
  ["agenda_title", "Заголовок: программа", 120, true],
  ["agenda_points", "Программа (один пункт на строку, максимум 6)", 280, false],
  ["speaker_title", "Заголовок: организатор", 120, true],
  ["speaker_text", "Об организаторе", 1200, false],
  ["faq_title", "Заголовок: вопросы", 120, true],
  ["cta_title", "Заголовок: участие", 180, true],
  ["cta_text", "Как получить доступ или записаться", 600, false]
];
const MULTILINE = new Set(["hero_subtitle", "audience_points", "outcome_points", "agenda_points", "speaker_text", "cta_text"]);

function asEditor(content) {
  const value = content || START_CONTENT;
  return {
    ...START_CONTENT,
    ...value,
    audience_points: (value.audience_points || "").constructor === Array ? value.audience_points.join("\n") : String(value.audience_points || ""),
    outcome_points: (value.outcome_points || "").constructor === Array ? value.outcome_points.join("\n") : String(value.outcome_points || ""),
    agenda_points: (value.agenda_points || "").constructor === Array ? value.agenda_points.join("\n") : String(value.agenda_points || ""),
    faq: Array.isArray(value.faq) ? value.faq.map((item) => ({ question: item.question || "", answer: item.answer || "" })) : []
  };
}

function toPayload(editor) {
  const list = (text) => String(text || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  const content = {
    ...editor,
    audience_points: list(editor.audience_points),
    outcome_points: list(editor.outcome_points),
    agenda_points: list(editor.agenda_points),
    faq: editor.faq.filter((item) => item.question.trim() || item.answer.trim())
  };
  for (const key of ["audience_points", "outcome_points", "agenda_points"]) {
    if (content[key].length > 6) throw new Error("В каждом списке допускается не более 6 пунктов.");
  }
  if (content.faq.length > 6 || content.faq.some((item) => !item.question.trim() || !item.answer.trim())) {
    throw new Error("Заполните вопрос и ответ для каждого пункта FAQ (не более 6).");
  }
  return content;
}

function publicLink(tenantId, businessId, eventId) {
  const url = new URL(window.location.origin + window.location.pathname);
  url.searchParams.set("event_tenant", tenantId);
  url.searchParams.set("event_business", businessId);
  url.searchParams.set("event_id", eventId);
  return url.toString();
}

export function EventLandingWorkspace({ apiBase, tenantId, businessId, apiKey, getJson, postJson }) {
  const [eventId, setEventId] = useState("");
  const [snapshot, setSnapshot] = useState(null);
  const [editor, setEditor] = useState(() => asEditor());
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef(null);
  const currentId = eventId.trim();
  const loaded = Boolean(snapshot && snapshot.event_id === currentId);
  const published = loaded && snapshot.status === "published";
  const canPublish = loaded && !dirty && (!published || snapshot.has_unpublished_changes);
  const endpoint = apiBase.replace(/\/$/, "") + "/business-workspace/event-landings/" + encodeURIComponent(currentId);
  const headers = apiKey ? { "X-API-Key": apiKey } : {};
  let previewContent = null;
  try { previewContent = toPayload(editor); } catch { /* Form errors are shown on save, never crash the owner UI. */ }

  const changeEventId = (value) => {
    setEventId(value);
    setSnapshot(null);
    setEditor(asEditor());
    setDirty(false);
    setError("");
    setNotice("");
    pending.current = null;
  };

  const changeContent = (field, value) => {
    setEditor((old) => ({ ...old, [field]: value }));
    setDirty(true);
    setNotice("");
  };

  const refresh = async () => {
    if (!currentId || !apiKey || busy) return;
    setBusy("load");
    setError("");
    setNotice("");
    try {
      const result = await getJson(endpoint, headers);
      setSnapshot(result);
      setEditor(asEditor(result.draft));
      setDirty(false);
      pending.current = null;
      setNotice("Черновик и статус публикации загружены из BusinessAIOS.");
    } catch (reason) {
      if (reason.httpStatus === 404) {
        setSnapshot(null);
        setNotice("Для этого ID ещё нет страницы. Заполните форму и нажмите «Создать черновик».");
      } else {
        setError("Не удалось загрузить страницу: " + (reason.message || "ошибка сети"));
      }
    } finally {
      setBusy("");
    }
  };

  const commit = async (action) => {
    if (!apiKey || !currentId || busy) return;
    if (action !== "create" && !loaded) return;
    if ((action === "publish" || action === "unpublish") && dirty) {
      setError("Сначала сохраните изменения черновика. Несохранённые поля нельзя публиковать.");
      return;
    }
    let payload;
    try {
      payload = {
        action,
        ...(action === "create" || action === "save" ? { content: toPayload(editor), source: "manual" } : {}),
        ...(action === "create" ? {} : { expected_revision: snapshot.revision })
      };
    } catch (reason) {
      setError(reason.message);
      return;
    }
    // A retry after an ambiguous network failure must reuse exactly the same
    // idempotency key for the same action, revision and content.
    const signature = JSON.stringify([currentId, payload]);
    if (!pending.current || pending.current.signature !== signature) {
      pending.current = { signature, key: "landing-" + crypto.randomUUID() };
    }
    setBusy(action);
    setError("");
    setNotice("");
    try {
      const result = await postJson(endpoint, { ...payload, idempotency_key: pending.current.key }, headers);
      setSnapshot(result);
      setEditor(asEditor(result.draft));
      setDirty(false);
      pending.current = null;
      const names = { create: "Черновик создан", save: "Черновик сохранён", publish: "Опубликовано", unpublish: "Снято с публикации" };
      setNotice(names[action] + ". Подтверждено сервером (ревизия " + result.revision + ").");
    } catch (reason) {
      if (reason.httpStatus === 409) {
        setError("Конфликт: страница уже существует или её изменили в другом сеансе. Загрузите актуальную версию перед повторным действием.");
      } else {
        setError("Сервер не подтвердил действие: " + (reason.message || "ошибка сети") + ". Повтор того же действия использует прежний ключ.");
      }
    } finally {
      setBusy("");
    }
  };

  const adjustFaq = (index, key, value) => {
    setEditor((old) => ({
      ...old,
      faq: old.faq.map((item, i) => i === index ? { ...item, [key]: value } : item)
    }));
    setDirty(true);
  };

  return (
    <section className="panel event-landing-editor" aria-labelledby="business-event-landing-title">
      <div className="panel-title-row">
        <div><p className="eyebrow">Мероприятия</p><h2 id="business-event-landing-title">Страница мероприятия</h2></div>
        <span className="privacy-badge">Ваш черновик · канонический Event Store</span>
      </div>
      <p className="muted-text">Откройте мероприятие по его ID или создайте черновик. После сохранения можно опубликовать страницу, а затем снять её с публикации. Пока вы не нажали «Опубликовать», посетители не увидят черновик.</p>
      <div className="event-landing-id">
        <label>Идентификатор мероприятия
          <input aria-label="ID мероприятия" maxLength={200} value={eventId} onChange={(e) => changeEventId(e.target.value)} placeholder="Например, webinar-2026-10" />
        </label>
        <button type="button" className="ghost" disabled={!apiKey || !currentId || Boolean(busy)} onClick={refresh}>{busy === "load" ? "Загружаем…" : "Загрузить"}</button>
      </div>
      {!apiKey ? <p className="error-box">Сначала восстановите доступ владельца к кабинету.</p> : null}
      {error ? <div role="alert" className="error-box inline-error">{error}</div> : null}
      {notice ? <p role="status" className="event-landing-notice">{notice}</p> : null}
      {loaded ? <p className="muted-text">Ревизия: {snapshot.revision} · Статус: {published ? "опубликована" : "черновик"}{dirty ? " · есть несохранённые изменения" : ""}</p> : null}
      <div className="event-landing-fields">
        {EDITOR_FIELDS.map(([key, label, maxLength, required]) => (
          <label key={key}>{label}{required ? " *" : ""}
            {MULTILINE.has(key)
              ? <textarea value={editor[key]} rows={key === "speaker_text" ? 2 : 3} onChange={(e) => changeContent(key, e.target.value)} />
              : <input value={editor[key]} maxLength={maxLength} required={required} onChange={(e) => changeContent(key, e.target.value)} />}
          </label>
        ))}
        <label>Внешний вид страницы
          <select value={editor.theme} onChange={(e) => changeContent("theme", e.target.value)}>
            <option value="calm">Спокойный</option>
            <option value="bold">Выразительный</option>
            <option value="minimal">Минималистичный</option>
          </select>
        </label>
      </div>
      <h3>Вопросы посетителей</h3>
      {editor.faq.map((item, index) => (
        <div className="event-faq-editor" key={index}>
          <label>Вопрос <input maxLength={220} value={item.question} onChange={(e) => adjustFaq(index, "question", e.target.value)} /></label>
          <label>Ответ <textarea maxLength={700} rows={2} value={item.answer} onChange={(e) => adjustFaq(index, "answer", e.target.value)} /></label>
          <button className="ghost" type="button" onClick={() => changeContent("faq", editor.faq.filter((_, i) => index !== i))}>Удалить</button>
        </div>
      ))}
      <div className="event-landing-actions">
        <button className="ghost" type="button" disabled={editor.faq.length >= 6} onClick={() => changeContent("faq", [...editor.faq, { question: "", answer: "" }])}>Добавить вопрос</button>
        <button className="primary" type="button" disabled={!currentId || !apiKey || loaded || Boolean(busy)} onClick={() => commit("create")}>{busy === "create" ? "Создаём…" : "Создать черновик"}</button>
        <button className="primary" type="button" disabled={!loaded || !apiKey || Boolean(busy) || !dirty} onClick={() => commit("save")}>{busy === "save" ? "Сохраняем…" : "Сохранить изменения"}</button>
        <button className="primary" type="button" disabled={!canPublish || Boolean(busy)} onClick={() => commit("publish")}>{busy === "publish" ? "Публикуем…" : "Опубликовать"}</button>
        <button className="ghost" type="button" disabled={!published || dirty || Boolean(busy)} onClick={() => commit("unpublish")}>Снять с публикации</button>
      </div>
      {loaded && published ? <p className="event-landing-notice">Публичная ссылка: <a href={publicLink(tenantId, businessId, currentId)} target="_blank" rel="noopener noreferrer">{publicLink(tenantId, businessId, currentId)}</a></p> : null}
      <details className="event-landing-preview" open={false}>
        <summary>Предпросмотр текущих полей (не публичная публикация)</summary>
        {previewContent ? <EventLandingPreview content={previewContent} /> : <p role="status">Заполните все пары FAQ и сократите списки до шести пунктов для предпросмотра.</p>}
      </details>
      <small className="muted-text">Эта страница информирует о мероприятии. Приём регистраций и проведение платежей не включаются автоматически.</small>
    </section>
  );
}
