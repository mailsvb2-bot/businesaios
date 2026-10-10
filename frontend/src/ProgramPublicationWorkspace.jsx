import { useEffect, useRef, useState } from "react";

const newLesson = () => ({ title: "", content_kind: "link", content_ref: "" });
const KINDS = [
  ["link", "Ссылка"], ["text", "Текстовый материал"], ["audio", "Аудио"],
  ["video", "Видео"], ["document", "Документ"], ["image", "Изображение"],
  ["task", "Задание"], ["mixed", "Смешанный материал"]
];

/** Phase 18: atomic course publication; actual lesson delivery is not enabled. */
export function ProgramPublicationWorkspace({ apiBase, apiKey, tenantId, businessId, getJson, postJson }) {
  const [programs, setPrograms] = useState([]);
  const [title, setTitle] = useState("");
  const [lessons, setLessons] = useState([newLesson()]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef(null);
  const url = apiBase.replace(/\/$/, "") + "/business-workspace/programs";
  const headers = apiKey ? { "X-API-Key": apiKey } : {};

  useEffect(() => {
    let active = true;
    if (!apiKey) return () => { active = false; };
    getJson(url, headers)
      .then((result) => {
        if (!active) return;
        if (!Array.isArray(result?.programs)) throw new Error("Некорректный список программ.");
        setPrograms(result.programs);
      })
      .catch((reason) => {
        if (active) setError("Не удалось загрузить программы: " + (reason.message || "ошибка сети"));
      });
    return () => { active = false; };
  }, [url, apiKey, getJson]);

  const changeLesson = (index, field, value) => {
    pending.current = null;
    setLessons((current) => current.map((item, position) => (
      position === index ? { ...item, [field]: value } : item
    )));
  };

  const publish = async (event) => {
    event.preventDefault();
    if (!apiKey || busy || !title.trim() || lessons.some((item) => (
      !item.title.trim() || !item.content_ref.trim()
    ))) return;
    const payload = {
      title: title.trim(),
      lessons: lessons.map((item) => ({
        title: item.title.trim(), content_kind: item.content_kind,
        content_ref: item.content_ref.trim(),
      })),
    };
    const signature = JSON.stringify(payload);
    if (!pending.current || pending.current.signature !== signature) {
      pending.current = { signature, key: "program-" + crypto.randomUUID() };
    }
    setBusy("publish");
    setError("");
    setNotice("");
    try {
      const published = await postJson(url, {
        ...payload, idempotency_key: pending.current.key,
      }, headers);
      if (!published || published.tenant_id !== tenantId ||
          published.business_id !== businessId || published.status !== "active" ||
          published.title !== payload.title || !Array.isArray(published.lessons) ||
          published.lessons.length !== payload.lessons.length || !published.id) {
        throw new Error("Сервер не подтвердил публикацию; повтор сохранит номер операции.");
      }
      pending.current = null;
      setPrograms((existing) => [published, ...existing.filter((item) => item.id !== published.id)]);
      setTitle("");
      setLessons([newLesson()]);
      setNotice("Программа сохранена и опубликована в каталоге BusinessAIOS. Номер: " + published.id);
      try {
        const refreshed = await getJson(url, headers);
        if (Array.isArray(refreshed?.programs)) setPrograms(refreshed.programs);
      } catch {
        // A failed refresh cannot undo a server-acknowledged publication.
      }
    } catch (reason) {
      setError("Публикация не подтверждена: " + (reason.message || "ошибка сети") +
        ". Повтор прежней операции использует тот же ключ.");
    } finally {
      setBusy("");
    }
  };

  const refresh = async () => {
    if (busy || !apiKey) return;
    setBusy("refresh");
    setError("");
    try {
      const result = await getJson(url, headers);
      if (!Array.isArray(result?.programs)) throw new Error("Некорректный список программ.");
      setPrograms(result.programs);
    } catch (reason) {
      setError("Не удалось обновить программы: " + (reason.message || "ошибка сети"));
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="panel" aria-labelledby="business-programs-title">
      <div className="panel-title-row">
        <div><p className="eyebrow">Материалы и программы</p>
          <h2 id="business-programs-title">Программы обучения</h2></div>
        <button type="button" className="ghost" onClick={refresh}
          disabled={!apiKey || Boolean(busy)}>Обновить каталог</button>
      </div>
      <p className="muted-text">Создайте программу с уроками. Публикация сохраняет программу в вашем бизнесе,
        но пока не отправляет материалы клиентам и не создаёт платёж.</p>
      <p className="muted-text">Не помещайте пароли, токены и персональные данные в ссылки или ссылки на материалы.</p>
      {error ? <p role="alert" className="error-box inline-error">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      <form onSubmit={publish}>
        <label>Название программы
          <input type="text" maxLength={200} value={title}
            disabled={Boolean(busy)}
            onChange={(event) => { setTitle(event.target.value); pending.current = null; }}
            placeholder="Например: Четыре шага к результату" />
        </label>
        <h3>Уроки ({lessons.length} из 100)</h3>
        {lessons.map((item, index) => (
          <fieldset key={index} disabled={Boolean(busy)}>
            <legend>Урок {index + 1}</legend>
            <label>Название урока
              <input type="text" maxLength={200} value={item.title}
                onChange={(event) => changeLesson(index, "title", event.target.value)} />
            </label>
            <label>Тип материала
              <select value={item.content_kind}
                onChange={(event) => changeLesson(index, "content_kind", event.target.value)}>
                {KINDS.map(([kind, name]) => <option key={kind} value={kind}>{name}</option>)}
              </select>
            </label>
            <label>Ссылка HTTPS или идентификатор сохранённого материала
              <input type="text" maxLength={2048} value={item.content_ref}
                onChange={(event) => changeLesson(index, "content_ref", event.target.value)} />
            </label>
            {lessons.length > 1 ? (
              <button type="button" className="ghost" onClick={() => {
                pending.current = null;
                setLessons((current) => current.filter((_, position) => position !== index));
              }}>Удалить урок {index + 1}</button>
            ) : null}
          </fieldset>
        ))}
        {lessons.length < 100 ? (
          <button type="button" className="ghost" disabled={Boolean(busy)} onClick={() => {
            pending.current = null;
            setLessons((current) => [...current, newLesson()]);
          }}>Добавить урок</button>
        ) : null}
        <button type="submit" className="primary"
          disabled={!apiKey || Boolean(busy) || !title.trim() ||
            lessons.some((item) => !item.title.trim() || !item.content_ref.trim())}>
          {busy === "publish" ? "Сохраняем…" : "Опубликовать программу"}
        </button>
      </form>
      <h3>Опубликованные программы</h3>
      {programs.length ? (
        <ul>{programs.map((item) => (
          <li key={item.id}>
            <strong>{item.title}</strong>
            <p>Уроков: {item.lessons.length} · Статус: {item.status}</p>
            <small>{item.id}</small>
            <ol>{item.lessons.map((lesson) => (
              <li key={lesson.position}>{lesson.title} · {lesson.content_kind}</li>
            ))}</ol>
          </li>
        ))}</ul>
      ) : <p className="muted-text">Программ пока нет.</p>}
    </section>
  );
}
