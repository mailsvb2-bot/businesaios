import { useEffect, useState } from "react";
import "./EventLandingWorkspace.css";

function SafeList({ items }) {
  return Array.isArray(items) && items.length
    ? <ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul>
    : <p>Информация появится после уточнения организатором.</p>;
}

export function EventLandingPreview({ content }) {
  if (!content) return null;
  return (
    <article className={"event-public-card theme-" + (content.theme || "calm")}>
      <header className="event-public-hero">
        <p className="eyebrow">{content.eyebrow}</p>
        <h1>{content.hero_title}</h1>
        {content.hero_subtitle ? <p>{content.hero_subtitle}</p> : null}
      </header>
      <div className="event-public-grid">
        <section><h2>{content.audience_title}</h2><SafeList items={content.audience_points} /></section>
        <section><h2>{content.outcomes_title}</h2><SafeList items={content.outcome_points} /></section>
        <section><h2>{content.agenda_title}</h2><SafeList items={content.agenda_points} /></section>
        <section><h2>{content.speaker_title}</h2><p>{content.speaker_text || "Будет указано организатором."}</p></section>
      </div>
      {Array.isArray(content.faq) && content.faq.length ? (
        <section className="event-public-faq"><h2>{content.faq_title}</h2>
          {content.faq.map((item, index) => <details key={index}><summary>{item.question}</summary><p>{item.answer}</p></details>)}
        </section>
      ) : null}
      <footer className="event-public-cta"><h2>{content.cta_title}</h2><p>{content.cta_text}</p></footer>
    </article>
  );
}

export function parsePublicEventQuery(search) {
  const params = new URLSearchParams(search);
  const eventId = params.get("event_id");
  const tenantId = params.get("event_tenant");
  const businessId = params.get("event_business");
  return eventId && tenantId && businessId ? { eventId, tenantId, businessId } : null;
}

export function PublicEventLanding({ apiBase, identity }) {
  const [state, setState] = useState({ loading: true, content: null, error: "" });
  useEffect(() => {
    let active = true;
    const endpoint = apiBase.replace(/\/$/, "") + "/public-site/events/"
      + encodeURIComponent(identity.tenantId) + "/" + encodeURIComponent(identity.businessId)
      + "/" + encodeURIComponent(identity.eventId);
    // This request is deliberately anonymous: the draft and owner's session
    // must never be sent to or rendered in the public participant page.
    fetch(endpoint, { credentials: "omit", cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(response.status === 404 ? "Страница ещё не опубликована или недоступна." : "Страница временно недоступна.");
        const payload = await response.json();
        if (!payload.ok || !payload.content) throw new Error("Публикация не подтверждена сервером.");
        return payload.content;
      })
      .then((content) => { if (active) setState({ loading: false, content, error: "" }); })
      .catch((error) => { if (active) setState({ loading: false, content: null, error: error.message }); });
    return () => { active = false; };
  }, [apiBase, identity.tenantId, identity.businessId, identity.eventId]);

  return (
    <main className="event-public-shell">
      <div className="event-public-brand">BusinessAIOS · Мероприятие</div>
      {state.loading ? <p role="status">Загружаем опубликованную страницу…</p> : null}
      {state.error ? <p role="alert" className="error-box">{state.error}</p> : null}
      {state.content ? <EventLandingPreview content={state.content} /> : null}
      <p className="event-public-footer">Данные страницы получены из опубликованной версии мероприятия.</p>
    </main>
  );
}
