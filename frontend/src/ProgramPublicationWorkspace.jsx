import { useEffect, useRef, useState } from "react";

const newLesson = () => ({ title: "", content_kind: "link", content_ref: "" });
const KINDS = [
  ["link", "Ссылка"], ["text", "Текстовый материал"], ["audio", "Аудио"],
  ["video", "Видео"], ["document", "Документ"], ["image", "Изображение"],
  ["task", "Задание"], ["mixed", "Смешанный материал"]
];

const PROVIDER_FOR_CHANNEL = { telegram: "telegram_bot", vk: "vk_messaging", max: "max_messaging", email: "email_connector", whatsapp: "whatsapp_cloud" };

function ProgramEnrollmentForm({ program, url, apiKey, customers, sendableProviders, onPrepareLessonSend, onRefreshCustomers, getJson, postJson }) {
  const activeCustomers = (customers || []).filter((customer) =>
    customer?.customer_id && customer?.status === "active"
  );
  const [customerId, setCustomerId] = useState("");
  const [enrollments, setEnrollments] = useState([]);
  const [busy, setBusy] = useState(false);
  const [deliveryChoice, setDeliveryChoice] = useState({});
  const [preparedNotice, setPreparedNotice] = useState("");
  const [error, setError] = useState("");
  const endpoint = url + "/" + encodeURIComponent(program.id) + "/enrollments";
  const headers = { "X-API-Key": apiKey };

  useEffect(() => {
    let active = true;
    if (apiKey) getJson(endpoint, headers).then((result) => {
      if (!active) return;
      if (!Array.isArray(result?.enrollments)) throw new Error("Некорректный список зачислений.");
      setEnrollments(result.enrollments);
    }).catch((reason) => {
      if (active) setError("Не удалось прочитать зачисления: " + (reason.message || "ошибка сети"));
    });
    return () => { active = false; };
  }, [apiKey, endpoint, getJson]);

  const enroll = async (event) => {
    event.preventDefault();
    if (busy || !apiKey || !customerId.trim() ||
        !activeCustomers.some((customer) => customer.customer_id === customerId)) return;
    setBusy(true);
    setError("");
    try {
      const receipt = await postJson(endpoint, { customer_id: customerId.trim() }, headers);
      if (receipt?.program_id !== program.id ||
          receipt?.customer_id !== customerId.trim() ||
          receipt?.status !== "awaiting_delivery" || !Array.isArray(receipt?.progress) ||
          receipt.progress.length !== program.lessons.length ||
          receipt.progress.some((item) => item.status !== "pending")) {
        throw new Error("Сервер не подтвердил зачисление в рамках программы.");
      }
      setEnrollments((existing) => [receipt, ...existing.filter((item) => item.id !== receipt.id)]);
      setCustomerId("");
    } catch (reason) {
      setError("Зачисление не подтверждено: " + (reason.message || "ошибка сети"));
    } finally {
      setBusy(false);
    }
  };

  const routesFor = (customerId) => {
    const customer = activeCustomers.find((item) => item.customer_id === customerId);
    return (customer?.identities || [])
      .filter((identity) => identity.status === "active" &&
        Boolean(identity.external_subject) &&
        sendableProviders.includes(PROVIDER_FOR_CHANNEL[identity.channel]))
      .map((identity) => identity.channel)
      .filter((channel, index, all) => all.indexOf(channel) === index);
  };

  const prepareLesson = async (enrollment, lesson, channel) => {
    if (busy || !channel || !onPrepareLessonSend) return;
    setBusy(true);
    setError("");
    setPreparedNotice("");
    try {
      await onPrepareLessonSend({
        programId: program.id, enrollmentId: enrollment.id,
        lessonPosition: lesson.position, channel,
      });
      setPreparedNotice("Урок подготовлен в Центре действий. Отправки и подтверждения доставки пока нет.");
    } catch (reason) {
      setError("Не удалось подготовить урок: " + (reason.message || "ошибка сети"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <form onSubmit={enroll}>
        <label>Выберите существующего клиента
          <select value={customerId}
            onChange={(event) => setCustomerId(event.target.value)}>
            <option value="">Выберите клиента из вашего бизнеса</option>
            {activeCustomers.map((customer) => (
              <option key={customer.customer_id} value={customer.customer_id}>
                {customer.display_name || customer.identities?.[0]?.display_name ||
                  customer.identities?.[0]?.username || customer.customer_id}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="ghost" disabled={busy || !apiKey}
          onClick={onRefreshCustomers}>Обновить список клиентов</button>
        {!activeCustomers.length ? (
          <p className="muted-text">Активных клиентов пока нет. Они появятся после входящих событий
            из подключённых каналов; вымышленных клиентов не создаём.</p>
        ) : null}
        <button type="submit" className="ghost" disabled={busy || !apiKey ||
          !activeCustomers.some((customer) => customer.customer_id === customerId)}>
          {busy ? "Зачисляем…" : "Зачислить без отправки материалов"}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {preparedNotice ? <p role="status">{preparedNotice}</p> : null}
      <p className="muted-text">Зачислено: {enrollments.length}. Для отправки урока используйте Центр действий:
        подготовка не означает согласие владельца, принятие провайдером или доставку клиенту.</p>
      {enrollments.map((enrollment) => {
        const channels = routesFor(enrollment.customer_id);
        const label = activeCustomers.find((customer) =>
          customer.customer_id === enrollment.customer_id)?.display_name || enrollment.customer_id;
        return (
          <div key={enrollment.id} className="recovery-box">
            <strong>Зачислен: {label}</strong>
            {!channels.length ? <p>Нет активной идентичности в подключённом канале с подтверждением владельца.</p> : null}
            {program.lessons.map((lesson) => {
              const key = enrollment.id + ":" + lesson.position;
              const channel = channels.includes(deliveryChoice[key]) ? deliveryChoice[key] : (channels[0] || "");
              const supported = ["text", "link"].includes(lesson.content_kind);
              return (
                <div key={key}>
                  <p>Урок {lesson.position}: {lesson.title} · Ожидает отправки</p>
                  {supported && channels.length ? (
                    <>
                      <label>Канал урока {lesson.position}
                        <select value={channel} disabled={busy}
                          onChange={(event) => setDeliveryChoice((current) => ({ ...current, [key]: event.target.value }))}>
                          {channels.map((item) => <option key={item} value={item}>{item}</option>)}
                        </select>
                      </label>
                      <button className="ghost" type="button" disabled={busy || !apiKey}
                        onClick={() => prepareLesson(enrollment, lesson, channel)}>
                        Подготовить урок {lesson.position} к отправке
                      </button>
                    </>
                  ) : !supported ? <p>Для этого типа материала требуется канонический медиамаршрут. Отправка заблокирована.</p> : null}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

/** Phase 18: atomic course publication; actual lesson delivery is not enabled. */
export function ProgramPublicationWorkspace({ apiBase, apiKey, tenantId, businessId, getJson, postJson, customers = [], sendableProviders = [], onPrepareLessonSend, onRefreshCustomers }) {
  const [programs, setPrograms] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [editingDraft, setEditingDraft] = useState(null);
  const [title, setTitle] = useState("");
  const [lessons, setLessons] = useState([newLesson()]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef(null);
  const draftPending = useRef(null);
  const url = apiBase.replace(/\/$/, "") + "/business-workspace/programs";
  const draftUrl = apiBase.replace(/\/$/, "") + "/business-workspace/program-drafts";
  const headers = apiKey ? { "X-API-Key": apiKey } : {};

  useEffect(() => {
    let active = true;
    if (!apiKey) return () => { active = false; };
    Promise.all([getJson(url, headers), getJson(draftUrl, headers)])
      .then(([result, saved]) => {
        if (!active) return;
        if (!Array.isArray(result?.programs) || !Array.isArray(saved?.drafts)) {
          throw new Error("Некорректный список программ.");
        }
        setPrograms(result.programs);
        setDrafts(saved.drafts);
      })
      .catch((reason) => {
        if (active) setError("Не удалось загрузить программы: " + (reason.message || "ошибка сети"));
      });
    return () => { active = false; };
  }, [url, draftUrl, apiKey, getJson]);

  const changeLesson = (index, field, value) => {
    pending.current = null;
    draftPending.current = null;
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
    if (editingDraft && editingDraft.signature !== signature) {
      setError("Сначала сохраните изменения черновика, затем публикуйте его.");
      return;
    }
    if (!pending.current || pending.current.signature !== (signature + ":" + (editingDraft?.id || "new"))) {
      pending.current = { signature: signature + ":" + (editingDraft?.id || "new"), key: "program-" + crypto.randomUUID() };
    }
    setBusy("publish");
    setError("");
    setNotice("");
    try {
      const published = editingDraft
        ? await postJson(draftUrl + "/" + encodeURIComponent(editingDraft.id), {
          action: "publish", expected_revision: editingDraft.revision,
          idempotency_key: pending.current.key,
        }, headers)
        : await postJson(url, {
          ...payload, idempotency_key: pending.current.key,
        }, headers);
      if (!published || published.tenant_id !== tenantId ||
          published.business_id !== businessId || published.status !== "active" ||
          published.title !== payload.title || !Array.isArray(published.lessons) ||
          published.lessons.length !== payload.lessons.length || !published.id) {
        throw new Error("Сервер не подтвердил публикацию; повтор сохранит номер операции.");
      }
      pending.current = null;
      draftPending.current = null;
      setEditingDraft(null);
      setDrafts((existing) => existing.filter((item) => item.id !== published.id));
      setPrograms((existing) => [published, ...existing.filter((item) => item.id !== published.id)]);
      setTitle("");
      setLessons([newLesson()]);
      setNotice("Программа сохранена и опубликована в каталоге BusinessAIOS. Номер: " + published.id);
      try {
        const [refreshed, remaining] = await Promise.all([
          getJson(url, headers), getJson(draftUrl, headers)
        ]);
        if (Array.isArray(refreshed?.programs)) setPrograms(refreshed.programs);
        if (Array.isArray(remaining?.drafts)) setDrafts(remaining.drafts);
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

  const clearEditor = () => {
    setEditingDraft(null);
    setTitle("");
    setLessons([newLesson()]);
    pending.current = null;
    draftPending.current = null;
    setError("");
    setNotice("");
  };

  const resetEditor = () => {
    if (busy) return;
    clearEditor();
  };

  const continueDraft = (draft) => {
    if (busy || !draft || draft.status !== "draft") return;
    const restoredLessons = (draft.lessons || []).map((item) => ({
      title: item.title, content_kind: item.content_kind, content_ref: item.content_ref,
    }));
    const normalized = { title: draft.title, lessons: restoredLessons };
    setTitle(draft.title);
    setLessons(restoredLessons.length ? restoredLessons : [newLesson()]);
    setEditingDraft({ id: draft.id, revision: draft.revision, signature: JSON.stringify(normalized) });
    pending.current = null;
    draftPending.current = null;
    setError("");
    setNotice("Черновик открыт. Изменения сохраняются только по кнопке «Сохранить черновик».");
  };

  const saveDraft = async () => {
    if (!apiKey || busy || !title.trim()) return;
    const raw = lessons.map((item) => ({
      title: item.title.trim(), content_kind: item.content_kind,
      content_ref: item.content_ref.trim(),
    }));
    const selected = raw.filter((item) => item.title || item.content_ref);
    if (selected.some((item) => !item.title || !item.content_ref)) {
      setError("Укажите и название, и материал каждого добавленного урока.");
      return;
    }
    const payload = { title: title.trim(), lessons: selected };
    const signature = JSON.stringify(payload);
    const requestSignature = (editingDraft?.id || "new") + ":" + signature;
    if (!draftPending.current || draftPending.current.signature !== requestSignature) {
      draftPending.current = {
        signature: requestSignature, key: "program-draft-" + crypto.randomUUID()
      };
    }
    setBusy("save-draft");
    setError("");
    setNotice("");
    try {
      const saved = editingDraft
        ? await postJson(draftUrl + "/" + encodeURIComponent(editingDraft.id), {
          action: "save", expected_revision: editingDraft.revision,
          ...payload, idempotency_key: draftPending.current.key,
        }, headers)
        : await postJson(draftUrl, {
          ...payload, idempotency_key: draftPending.current.key,
        }, headers);
      if (saved?.tenant_id !== tenantId || saved?.business_id !== businessId ||
          saved?.status !== "draft" || saved?.title !== payload.title ||
          !Array.isArray(saved?.lessons) || saved.lessons.length !== payload.lessons.length ||
          !Number.isInteger(saved?.revision) || saved.revision < 1 || !saved.id) {
        throw new Error("Сервер не подтвердил сохранение черновика.");
      }
      const refreshedSignature = JSON.stringify(payload);
      setEditingDraft({ id: saved.id, revision: saved.revision, signature: refreshedSignature });
      setDrafts((existing) => [saved, ...existing.filter((item) => item.id !== saved.id)]);
      draftPending.current = null;
      pending.current = null;
      setNotice("Черновик сохранён в BusinessAIOS. Его можно открыть позже. Номер: " + saved.id);
    } catch (reason) {
      setError("Черновик не подтверждён: " + (reason.message || "ошибка сети") +
        ". При повторе используется тот же ключ операции.");
    } finally {
      setBusy("");
    }
  };

  const archiveDraft = async (draft) => {
    if (!apiKey || busy || draft.status !== "draft") return;
    const signature = "archive:" + draft.id + ":" + draft.revision;
    if (!draftPending.current || draftPending.current.signature !== signature) {
      draftPending.current = { signature, key: "program-draft-" + crypto.randomUUID() };
    }
    setBusy("archive");
    setError("");
    try {
      const archived = await postJson(draftUrl + "/" + encodeURIComponent(draft.id), {
        action: "archive", expected_revision: draft.revision,
        idempotency_key: draftPending.current.key,
      }, headers);
      if (archived?.id !== draft.id || archived?.status !== "archived") {
        throw new Error("Архивирование не подтверждено сервером.");
      }
      draftPending.current = null;
      setDrafts((existing) => existing.filter((item) => item.id !== archived.id));
      // A server-acknowledged archive must close the editor even while this
      // request owns the busy flag; a user-initiated reset stays blocked.
      if (editingDraft?.id === archived.id) clearEditor();
      setNotice("Черновик архивирован. Опубликованные программы не затронуты.");
    } catch (reason) {
      setError("Не удалось архивировать черновик: " + (reason.message || "ошибка сети"));
    } finally {
      setBusy("");
    }
  };

  const refresh = async () => {
    if (busy || !apiKey) return;
    setBusy("refresh");
    setError("");
    try {
      const [result, saved] = await Promise.all([getJson(url, headers), getJson(draftUrl, headers)]);
      if (!Array.isArray(result?.programs) || !Array.isArray(saved?.drafts)) {
        throw new Error("Некорректный список программ.");
      }
      setPrograms(result.programs);
      setDrafts(saved.drafts);
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
      <div className="navigation-row">
        <button type="button" className="ghost" disabled={Boolean(busy)} onClick={resetEditor}>Новая программа</button>
      </div>
      {editingDraft ? <p role="status">Редактируется черновик {editingDraft.id} · Версия: {editingDraft.revision}</p> : null}
      <form onSubmit={publish}>
        <label>Название программы
          <input type="text" maxLength={200} value={title}
            disabled={Boolean(busy)}
            onChange={(event) => { setTitle(event.target.value); pending.current = null; draftPending.current = null; }}
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
                draftPending.current = null;
                setLessons((current) => current.filter((_, position) => position !== index));
              }}>Удалить урок {index + 1}</button>
            ) : null}
          </fieldset>
        ))}
        {lessons.length < 100 ? (
          <button type="button" className="ghost" disabled={Boolean(busy)} onClick={() => {
            pending.current = null;
            draftPending.current = null;
            setLessons((current) => [...current, newLesson()]);
          }}>Добавить урок</button>
        ) : null}
        <button type="button" className="ghost" onClick={saveDraft}
          disabled={!apiKey || Boolean(busy) || !title.trim()}> 
          {busy === "save-draft" ? "Сохраняем черновик…" : "Сохранить черновик"}
        </button>
        <button type="submit" className="primary"
          disabled={!apiKey || Boolean(busy) || !title.trim() ||
            lessons.some((item) => !item.title.trim() || !item.content_ref.trim())}>
          {busy === "publish" ? "Сохраняем…" : editingDraft ? "Опубликовать черновик" : "Опубликовать программу"}
        </button>
      </form>
      <h3>Сохранённые черновики</h3>
      {drafts.length ? (
        <ul>{drafts.map((draft) => (
          <li key={draft.id}>
            <strong>{draft.title}</strong>
            <p>Уроков: {draft.lessons.length} · Версия: {draft.revision}</p>
            <div className="navigation-row">
              <button type="button" className="ghost" disabled={Boolean(busy)}
                onClick={() => continueDraft(draft)}>Продолжить черновик</button>
              <button type="button" className="ghost" disabled={Boolean(busy)}
                onClick={() => archiveDraft(draft)}>Архивировать черновик</button>
            </div>
          </li>
        ))}</ul>
      ) : <p className="muted-text">Черновиков пока нет.</p>}
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
            <ProgramEnrollmentForm key={item.id} program={item} url={url}
              apiKey={apiKey} customers={customers} sendableProviders={sendableProviders}
              onPrepareLessonSend={onPrepareLessonSend} onRefreshCustomers={onRefreshCustomers}
              getJson={getJson} postJson={postJson} />
          </li>
        ))}</ul>
      ) : <p className="muted-text">Программ пока нет.</p>}
    </section>
  );
}
