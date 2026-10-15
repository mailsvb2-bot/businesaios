import { useState } from "react";

const empty = {
  campaign_id: "", headline: "", description: "", brand_context: "",
  campaign_goal: "", kind: "image", formats: ["square", "story"],
};

export function AdvertisingStudioWorkspace({ apiBase, apiKey, postJson }) {
  const [brief, setBrief] = useState(empty);
  const [drafts, setDrafts] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const change = (field) => (event) => {
    setBrief((current) => ({ ...current, [field]: event.target.value }));
    setDrafts([]);
    setError("");
  };
  const prepare = async (event) => {
    event.preventDefault();
    if (!apiKey || busy) return;
    setBusy(true);
    setError("");
    setDrafts([]);
    try {
      const response = await postJson(
        apiBase.replace(/\/$/, "") + "/business-workspace/commercial/advertising/creatives/prepare",
        brief, { "X-API-Key": apiKey },
      );
      if (response.draft_only !== true || response.generation_submitted !== false ||
          response.spend_authorized !== false || !Array.isArray(response.creatives)) {
        throw new Error("Сервер не подтвердил безопасный режим подготовки");
      }
      setDrafts(response.creatives);
    } catch (reason) {
      setError("Не удалось подготовить варианты рекламы: " + reason.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel" aria-labelledby="advertising-studio-title">
      <p className="eyebrow">Реклама · творческая мастерская</p>
      <h2 id="advertising-studio-title">Подготовить изображения и видео для рекламы</h2>
      <p className="muted-text">Здесь создаются задания и варианты креативов. Реальная генерация медиа и запуск рекламных кампаний пока недоступны; деньги не расходуются.</p>
      <form onSubmit={prepare}>
        <label>Идентификатор кампании<input required maxLength={128} value={brief.campaign_id} onChange={change("campaign_id")} /></label>
        <label>Заголовок<input required maxLength={160} value={brief.headline} onChange={change("headline")} /></label>
        <label>Описание услуги<textarea required maxLength={500} value={brief.description} onChange={change("description")} /></label>
        <label>Стиль и бренд<textarea required maxLength={4000} value={brief.brand_context} onChange={change("brand_context")} /></label>
        <label>Цель кампании<input required maxLength={280} value={brief.campaign_goal} onChange={change("campaign_goal")} /></label>
        <label>Формат креатива<select value={brief.kind} onChange={change("kind")}><option value="image">Изображение</option><option value="video">Видео</option></select></label>
        <button type="submit" className="primary" disabled={!apiKey || busy}>{busy ? "Готовим варианты…" : "Подготовить рекламные варианты"}</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {drafts.length ? <div role="status">
        <h3>Варианты для согласования</h3>
        {drafts.map((item) => <article key={item.creative_id} className="panel">
          <strong>{item.angle} · {item.kind === "video" ? "Видео" : "Изображение"}</strong>
          <p>{item.prompt}</p>
          <small>Код варианта: {item.creative_id}. Не отправлено генератору, не опубликовано.</small>
        </article>)}
      </div> : null}
    </section>
  );
}
