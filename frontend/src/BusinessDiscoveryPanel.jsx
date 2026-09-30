import { useEffect, useMemo, useState } from "react";
import "./BusinessDiscoveryPanel.css";

const FIELD_COPY = {
  "identity.display_name": { title: "Название бизнеса в профиле", help: "Как владелец называет этот бизнес для работы внутри BusinessAIOS." },
  "identity.website": { title: "Сайт или публичная страница", help: "Основной адрес, по которому можно проверить публичную информацию о бизнесе." },
  "identity.industry": { title: "Сфера бизнеса", help: "Помогает не применять к вашему бизнесу нерелевантные отраслевые предположения." },
  "identity.business_model": { title: "Модель бизнеса", help: "Например: услуги, товары, B2B, маркетплейс или смешанная модель." },
  "market.city": { title: "Основной город", help: "Где находится основная операционная точка или рынок бизнеса." },
  "market.region": { title: "Регион или рынок", help: "Территория, на которой вы в основном работаете или продаёте." },
  "offer.summary": { title: "Что вы продаёте", help: "Коротко опишите основной продукт или услугу." },
  "economics.average_check": { title: "Средний чек", help: "Можно указать приблизительно. Сумма хранится в минимальных единицах валюты, чтобы не терять точность." },
  "economics.margin_pct": { title: "Маржа, %", help: "Если точной цифры нет, можно выбрать «Не знаю»." },
  "sales.has_clients": { title: "Есть ли уже клиенты", help: "Это помогает отличить запуск с нуля от роста существующего бизнеса." },
  "acquisition.test_budget_7d": { title: "Тестовый бюджет на 7 дней", help: "Укажите только если такой лимит действительно существует; иначе можно выбрать «Не знаю»." }
};

const CLIENT_OPTIONS = [
  ["", "Выберите вариант"],
  ["yes", "Да, есть регулярные клиенты"],
  ["some", "Есть первые или нерегулярные клиенты"],
  ["no", "Клиентов пока нет"]
];

function fieldCopy(field) {
  return FIELD_COPY[field?.key] || { title: field?.key || "Следующий вопрос", help: "Ответ помогает уточнить модель бизнеса." };
}

function statusLabel(field) {
  if (field?.conflict || field?.epistemic_status === "CONFLICTED") return "Есть расхождение с источником";
  if (field?.epistemic_status === "VERIFIED") return "Подтверждено источником";
  if (field?.provider_observed) return "Получено из источника";
  if (field?.owner_asserted) return "Со слов владельца";
  if (field?.status === "unknown") return "Пока неизвестно";
  return "Учтено";
}

function statusClass(field) {
  if (field?.conflict || field?.epistemic_status === "CONFLICTED") return "conflict";
  if (field?.epistemic_status === "VERIFIED") return "verified";
  if (field?.provider_observed) return "provider";
  if (field?.owner_asserted) return "owner";
  return "neutral";
}

function initialDraft(field) {
  if (field?.value_kind === "money_minor") return { amount_minor: "", currency: "RUB" };
  if (field?.value_kind === "client_presence") return { choice: "" };
  return { value: "" };
}

function knownValue(field, draft) {
  if (field.value_kind === "money_minor") {
    const raw = String(draft.amount_minor || "").trim();
    const currency = String(draft.currency || "").trim().toUpperCase();
    if (!/^\d+$/.test(raw) || !/^[A-Z]{3}$/.test(currency)) return null;
    const amount = Number(raw);
    if (!Number.isSafeInteger(amount) || amount < 0) return null;
    return { amount_minor: amount, currency };
  }
  if (field.value_kind === "percentage") {
    const raw = String(draft.value || "").trim();
    if (!raw) return null;
    const value = Number(raw.replace(",", "."));
    if (!Number.isFinite(value) || value < 0 || value > 100) return null;
    return value;
  }
  if (field.value_kind === "client_presence") {
    return String(draft.choice || "").trim() || null;
  }
  const text = String(draft.value || "").trim();
  return text || null;
}

export function BusinessDiscoveryPanel({ enabled, onLoad, onAssert }) {
  const [snapshot, setSnapshot] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [skipped, setSkipped] = useState([]);
  const fields = Array.isArray(snapshot?.fields) ? snapshot.fields : [];
  const remaining = fields.filter((field) => !field.covered);
  const nextField = remaining.find((field) => !skipped.includes(field.key)) || null;
  const [draft, setDraft] = useState({ value: "" });

  const progressPercent = useMemo(() => {
    const total = Number(snapshot?.progress?.total_fields || 0);
    const covered = Number(snapshot?.progress?.covered_fields || 0);
    return total > 0 ? Math.round((covered / total) * 100) : 0;
  }, [snapshot]);

  const reload = async () => {
    if (!enabled) return null;
    setBusy(true);
    setError("");
    try {
      const payload = await onLoad();
      setSnapshot(payload);
      return payload;
    } catch {
      setError("Не удалось загрузить знакомство с бизнесом. Другие функции кабинета остаются доступны.");
      return null;
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!enabled) return;
    void reload();
  }, [enabled, onLoad]);

  useEffect(() => {
    setDraft(initialDraft(nextField));
  }, [nextField?.key]);

  const submit = async (unknown = false) => {
    if (!nextField || busy) return;
    const value = unknown ? null : knownValue(nextField, draft);
    if (!unknown && value === null) {
      setError("Заполните ответ в указанном формате или выберите «Не знаю».");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const payload = {
        field_key: nextField.key,
        value,
        unknown,
        observed_at_ms: Date.now()
      };
      const next = await onAssert(payload, crypto.randomUUID());
      setSnapshot(next);
      setSkipped((items) => items.filter((key) => key !== nextField.key));
    } catch (err) {
      setError(String(err?.message || "Не удалось сохранить ответ. Повторите попытку."));
    } finally {
      setBusy(false);
    }
  };

  const skipCurrent = () => {
    if (!nextField) return;
    setSkipped((items) => items.includes(nextField.key) ? items : [...items, nextField.key]);
    setError("");
  };

  if (!enabled) return null;

  const answered = fields.filter((field) => field.covered);
  const copy = fieldCopy(nextField);
  const allTemporarilySkipped = remaining.length > 0 && nextField === null;

  return (
    <section className="panel discovery-panel" aria-labelledby="business-discovery-title">
      <div className="panel-title-row">
        <div>
          <p className="eyebrow">Модель бизнеса</p>
          <h2 id="business-discovery-title">Знакомство с бизнесом</h2>
          <p className="muted-text">По одному вопросу за раз. Ответы становятся фактами с источником, а данные подключённых систем могут их подтвердить или показать расхождение.</p>
        </div>
        <span className="discovery-percent">{progressPercent}%</span>
      </div>

      <div className="discovery-progress">
        <div className="discovery-progress-track" role="progressbar" aria-label="Прогресс знакомства с бизнесом" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progressPercent}>
          <span style={{ width: `${progressPercent}%` }} />
        </div>
        <small>{snapshot?.progress ? `${snapshot.progress.covered_fields} из ${snapshot.progress.total_fields} фактов уточнено` : "Загружаем факты…"}</small>
      </div>

      {error ? <div className="error-box inline-error" role="alert">{error}</div> : null}

      {nextField ? (
        <div className="discovery-question" data-discovery-field-key={nextField.key}>
          <div>
            <small>Следующий вопрос</small>
            <h3>{copy.title}</h3>
            <p>{copy.help}</p>
          </div>

          {nextField.value_kind === "money_minor" ? (
            <div className="discovery-money-grid">
              <label>Сумма в минимальных единицах
                <input aria-label="Сумма в минимальных единицах" inputMode="numeric" value={draft.amount_minor || ""} onChange={(event) => setDraft((current) => ({ ...current, amount_minor: event.target.value }))} placeholder="Например, 150000" />
              </label>
              <label>Валюта
                <input aria-label="Валюта" value={draft.currency || ""} maxLength={3} onChange={(event) => setDraft((current) => ({ ...current, currency: event.target.value.toUpperCase() }))} placeholder="RUB" />
              </label>
              <small className="discovery-format-note">Используем минимальные единицы валюты (копейки/центы), чтобы не терять точность. Для валют без дробной части — целое значение.</small>
            </div>
          ) : nextField.value_kind === "percentage" ? (
            <label>{copy.title}
              <input aria-label={copy.title} inputMode="decimal" value={draft.value || ""} onChange={(event) => setDraft({ value: event.target.value })} placeholder="0–100" />
            </label>
          ) : nextField.value_kind === "client_presence" ? (
            <label>{copy.title}
              <select aria-label={copy.title} value={draft.choice || ""} onChange={(event) => setDraft({ choice: event.target.value })}>
                {CLIENT_OPTIONS.map(([value, label]) => <option value={value} key={value || "empty"}>{label}</option>)}
              </select>
            </label>
          ) : (
            <label>{copy.title}
              <input aria-label={copy.title} value={draft.value || ""} onChange={(event) => setDraft({ value: event.target.value })} />
            </label>
          )}

          <div className="discovery-actions">
            <button type="button" className="primary" disabled={busy} onClick={() => void submit(false)}>{busy ? "Сохраняем…" : "Сохранить ответ"}</button>
            <button type="button" className="ghost" disabled={busy} onClick={() => void submit(true)}>Не знаю</button>
            <button type="button" className="ghost" disabled={busy} onClick={skipCurrent}>Пропустить сейчас</button>
          </div>
          <small className="helper-text">«Пропустить сейчас» ничего не записывает и вернёт вопрос после обновления страницы. «Не знаю» сохраняется как явный факт неизвестности.</small>
        </div>
      ) : snapshot?.progress?.complete ? (
        <div className="discovery-complete" role="status"><strong>Базовое знакомство завершено</strong><span>Если подключённый источник уточнит данные, здесь появится подтверждение или видимое расхождение.</span></div>
      ) : allTemporarilySkipped ? (
        <div className="discovery-complete"><strong>Оставшиеся вопросы пока пропущены</strong><span>Они не считаются отвеченными и вернутся после обновления страницы.</span><button type="button" className="ghost small" onClick={() => setSkipped([])}>Вернуть вопросы сейчас</button></div>
      ) : busy ? <div className="loading-box">Загружаем знакомство с бизнесом…</div> : null}

      {answered.length ? (
        <details className="discovery-known-facts">
          <summary>Что BusinessAIOS уже знает <strong>{answered.length}</strong></summary>
          <div className="discovery-fact-list">
            {answered.map((field) => (
              <div className="discovery-fact-row" key={field.key}>
                <div><strong>{fieldCopy(field).title}</strong><small>{field.status === "unknown" ? "Значение пока неизвестно" : typeof field.value === "object" ? JSON.stringify(field.value) : String(field.value ?? "")}</small></div>
                <span className={`discovery-status ${statusClass(field)}`}>{statusLabel(field)}</span>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      {!snapshot && !busy && !error ? <button type="button" className="ghost small" onClick={() => void reload()}>Загрузить вопросы</button> : null}
    </section>
  );
}
