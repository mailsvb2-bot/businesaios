"""Event warm-ups (before start) and consent-aware sales follow-ups (after end).

Ported from clientplatform ``event_warmups`` + ``event_followups`` onto booked slots
(``bookings@v1``). Facts live in ``event_series@v1``. Warm-ups are organizational
messages to the person who booked (no links, no selling). Follow-ups are commercial:
they go out only with the participant's explicit opt-in (/offers_on, revocable with
/offers_off), only for a known attendance segment (unknown = nothing, fail-closed),
within a grace window, and every dispatch key is sent at most once.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from application.business_flows import brand_discovery, visual_creatives
from application.business_flows.projection import stable_id

CANON_EVENT_SERIES_FLOW = True
HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS
GRACE_MS = 36 * HOUR_MS
DEFAULT_WARMUP_DAYS = (3, 1)
MAX_TEXT = 1000
FOLLOWUP_STAGES = {
    "attended_unpaid": ((1, HOUR_MS), (2, 24 * HOUR_MS), (3, 48 * HOUR_MS)),
    "no_show": ((1, HOUR_MS), (2, 24 * HOUR_MS)),
}
SEGMENT_LABEL = {"attended_unpaid": "были на встрече", "no_show": "не пришли"}
_FOLLOWUP_TEMPLATES = {
    ("attended_unpaid", 1): "Спасибо, что были на «{title}».\n\nПродолжить и посмотреть предложение: {offer}",
    ("attended_unpaid", 2): "Напомню о продолжении темы «{title}» без искусственной срочности. Подробности: {offer}",
    ("attended_unpaid", 3): "Это последнее сообщение в серии после «{title}». Если захотите продолжить позже: {offer}",
    ("no_show", 1): "Вы записывались на «{title}», но участие не подтвердилось. Если тема актуальна: {offer}",
    ("no_show", 2): "Это последнее напоминание по записи на «{title}»: {offer}",
}
_WARMUP_TEMPLATE = "До «{title}» осталось {days}. Подготовьте вопросы — разберём их на встрече."
_UNSAFE = re.compile(r"https?://|www\.|t\.me/|@\w{4,}|\b(купи|оплат|скидк|промокод)", re.IGNORECASE)


@dataclass
class State:
    consent: dict[str, bool] = field(default_factory=dict)
    texts: dict[tuple[str, str, int], str] = field(default_factory=dict)
    attendance: dict[tuple[str, str], str] = field(default_factory=dict)
    sent: set[str] = field(default_factory=set)
    warmup_days: tuple[int, ...] = DEFAULT_WARMUP_DAYS
    followups_on: bool = True
    segments_off: set[str] = field(default_factory=set)
    content_modes: dict[tuple[str, str], str] = field(default_factory=dict)
    assets: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    media_queued: set[str] = field(default_factory=set)


def expand(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten ``batch`` payloads (one tracked message that carries several facts)."""
    return [x for p in payloads for x in (p.get("facts") or [] if p.get("step") == "batch" else [p])]


def replay(payloads: list[dict[str, Any]]) -> State:
    st = State()
    for p in expand(payloads):
        step = p.get("step")
        if step == "offers_consent":
            st.consent[str(p["customer_id"])] = bool(p["on"])
        elif step == "text_set":
            st.texts[(p["kind"], p["segment"], int(p["stage"]))] = str(p["text"])
        elif step == "text_reset":
            st.texts.pop((p["kind"], p["segment"], int(p["stage"])), None)
        elif step == "followups_toggle":
            st.followups_on = bool(p["on"])
        elif step == "followup_segment":
            (st.segments_off.discard if p["on"] else st.segments_off.add)(str(p["segment"]))
        elif step == "attendance":
            st.attendance[(p["slot_id"], p["customer_id"])] = str(p["status"])
        elif step == "series_sent":
            st.sent.add(str(p["key"]))
        elif step == "event_content_mode":
            st.content_modes[(str(p["event_id"]), str(p["stage"]))] = str(p["mode"])
        elif step == "event_asset_set":
            k = (str(p["event_id"]), str(p["stage"]), str(p["slot_key"]))
            prev = st.assets.get(k)
            st.assets[k] = {**{x: p[x] for x in ("kind", "media_reference", "source", "source_ref")},
                            "revision": (prev["revision"] + 1) if prev else 1}
        elif step == "event_media_queued":
            st.media_queued.add(str(p["key"]))
        elif step == "warmup_days":
            st.warmup_days = tuple(int(d) for d in p["days"])
    return st


def _days(n: int) -> str:
    return {1: "1 день", 2: "2 дня", 3: "3 дня", 4: "4 дня"}.get(n, f"{n} дней")


def safe_warmup_text(text: str) -> str:
    """Warm-ups are organizational: reject links, handles and selling words."""
    value = " ".join(str(text or "").split())[:MAX_TEXT]
    if not value:
        raise ValueError("text_empty")
    if _UNSAFE.search(value):
        raise ValueError("warmup_text_must_not_sell_or_link")
    return value


def parse_warmup_days(arg: str) -> dict[str, Any]:
    days = sorted({int(x) for x in re.findall(r"\d+", str(arg or ""))}, reverse=True)
    if not days or len(days) > 5 or not all(1 <= d <= 30 for d in days):
        raise ValueError("warmup_days_format: /warmup_days 3,1 (1..30, до 5 значений)")
    return {"step": "warmup_days", "days": days}


def _stage_ref(arg: str) -> tuple[str, str, int, str]:
    head, _, text = str(arg or "").partition("|")
    parts = head.split()
    if len(parts) != 3 or not parts[2].isdigit():
        raise ValueError("series_text_format: /series_text followup attended_unpaid 1 | текст")
    kind, segment, stage = parts[0].casefold(), parts[1].casefold(), int(parts[2])
    if kind == "warmup" and segment == "all" and 1 <= stage <= 5:
        return kind, segment, stage, text.strip()
    if kind == "followup" and stage in dict(FOLLOWUP_STAGES.get(segment, ())):
        return kind, segment, stage, text.strip()
    raise ValueError("series_stage_unknown")


def set_text(arg: str) -> dict[str, Any]:
    kind, segment, stage, text = _stage_ref(arg)
    text = safe_warmup_text(text) if kind == "warmup" else " ".join(text.split())[:MAX_TEXT]
    if not text:
        raise ValueError("text_empty")
    if kind == "followup" and "{offer}" not in text:
        raise ValueError("followup_text_needs_{offer}")
    return {"step": "text_set", "kind": kind, "segment": segment, "stage": stage, "text": text}


def reset_text(arg: str) -> dict[str, Any]:
    kind, segment, stage, _ = _stage_ref(arg)
    return {"step": "text_reset", "kind": kind, "segment": segment, "stage": stage}


def consent(customer_id: str, on: bool) -> dict[str, Any]:
    return {"step": "offers_consent", "customer_id": customer_id, "on": bool(on)}


def mark_attendance(slot: Any, status: str, *, now_ms: int) -> dict[str, Any]:
    if status not in ("attended", "no_show"):
        raise ValueError("attendance_format: /attendance N attended|no_show")
    if slot is None or slot.status != "booked" or slot.starts_at_ms > now_ms:
        raise ValueError("attendance_slot_not_past_booking")
    return {"step": "attendance", "slot_id": slot.slot_id, "customer_id": slot.customer_id, "status": status}


def _template(st: State, kind: str, segment: str, stage: int) -> tuple[str, str]:
    custom = st.texts.get((kind, segment, stage))
    if custom:
        return custom, "owner"
    return (_WARMUP_TEMPLATE if kind == "warmup" else _FOLLOWUP_TEMPLATES[(segment, stage)]), "template"


def previews(st: State) -> list[str]:
    rows = [
        f"warmup all {i} (за {_days(d)}) [{_template(st, 'warmup', 'all', i)[1]}]: {_template(st, 'warmup', 'all', i)[0]}"
        for i, d in enumerate(st.warmup_days, 1)
    ]
    for segment, stages in FOLLOWUP_STAGES.items():
        for stage, offset in stages:
            text, src = _template(st, "followup", segment, stage)
            rows.append(
                f"followup {segment} {stage} (+{offset // HOUR_MS} ч, {SEGMENT_LABEL[segment]}) [{src}]: {text}"
            )
    return rows


def followup_allowed(st: State, segment: str) -> bool:
    """Donor event_followups_enabled_in_conn: master switch plus per-segment switch."""
    return st.followups_on and segment not in st.segments_off


def followup_settings(st: State, arg: str) -> dict[str, Any]:
    """Donor set_business_event_followups_enabled / _segment_enabled.

    ``on|off`` toggles the whole series; ``<segment> on|off`` one audience group.
    Turning something off takes effect immediately for every not-yet-sent message,
    because due_messages consults these settings at dispatch time (donor cancels the
    pending outbox rows). The last enabled group cannot be turned off while the series
    is on — turn the series off instead.
    """
    parts = str(arg or "").split()
    if len(parts) == 1 and parts[0] in ("on", "off"):
        on = parts[0] == "on"
        if on and set(FOLLOWUP_STAGES) <= st.segments_off:
            raise ValueError("followups_need_segment: включите хотя бы одну группу")
        return {"step": "followups_toggle", "on": on}
    if len(parts) == 2 and parts[0] in FOLLOWUP_STAGES and parts[1] in ("on", "off"):
        on = parts[1] == "on"
        left = set(FOLLOWUP_STAGES) - st.segments_off - {parts[0]}
        if not on and st.followups_on and not left:
            raise ValueError("followups_last_segment: нужна хотя бы одна группа (или /followups off)")
        return {"step": "followup_segment", "segment": parts[0], "on": on}
    raise ValueError("followups_format: /followups on|off или /followups no_show|attended_unpaid on|off")


def followup_status(st: State) -> str:
    rows = ["🔁 Догоняющие сообщения: " + ("включены" if st.followups_on else "выключены")]
    rows += [f"• {SEGMENT_LABEL[s]} ({s}): " + ("да" if s not in st.segments_off else "нет") for s in FOLLOWUP_STAGES]
    return "\n".join(rows)


def segment_of(st: State, slot: Any) -> str | None:
    status = st.attendance.get((slot.slot_id, slot.customer_id))
    return {"attended": "attended_unpaid", "no_show": "no_show"}.get(status or "")


def due_messages(st: State, slots: dict[str, Any], *, now_ms: int, offer_url: str = "") -> list[dict[str, Any]]:
    """Every message whose time has come, not yet sent; each carries its idempotent key."""
    out: list[dict[str, Any]] = []
    for slot in slots.values():
        if slot.status != "booked" or not slot.customer_id:
            continue
        for i, days in enumerate(st.warmup_days, 1):
            at = slot.starts_at_ms - days * DAY_MS
            key = stable_id("warm", slot.slot_id, slot.customer_id, days)
            if at <= now_ms < slot.starts_at_ms and key not in st.sent:
                text = _template(st, "warmup", "all", i)[0].format(title=slot.title, days=_days(days))
                out.append({"key": key, "to": slot.customer_id, "kind": "warmup", "text": text})
        segment = segment_of(st, slot)
        if not segment or not followup_allowed(st, segment) or not offer_url or not st.consent.get(slot.customer_id):
            continue
        end = slot.starts_at_ms + slot.duration_min * 60_000
        for stage, offset in FOLLOWUP_STAGES[segment]:
            at, key = end + offset, stable_id("follow", slot.slot_id, slot.customer_id, segment, stage)
            if at <= now_ms <= at + GRACE_MS and key not in st.sent:
                text = _template(st, "followup", segment, stage)[0].format(title=slot.title, offer=offer_url)
                out.append(
                    {
                        "key": key,
                        "to": slot.customer_id,
                        "kind": "followup",
                        "text": text + "\n\nОтписаться: /offers_off",
                    }
                )
                break  # one follow-up per participant per run
    return out


CHANNEL_PRIORITY_ENV = "BAI_EVENT_FOLLOWUP_CHANNEL_PRIORITY"
DEFAULT_CHANNEL_PRIORITY = ("max", "vk", "telegram", "email")


def channel_priority(env: dict[str, str] | None = None) -> tuple[str, ...]:
    """Port of event_warmups/event_followups._channel_priority (unknown/duplicate entries dropped)."""
    import os
    raw = str((os.environ if env is None else env).get(CHANNEL_PRIORITY_ENV) or "").strip()
    out: list[str] = []
    for part in raw.split(","):
        v = part.strip().lower()
        if v in DEFAULT_CHANNEL_PRIORITY and v not in out:
            out.append(v)
    return tuple(out) or DEFAULT_CHANNEL_PRIORITY


def pick_channel(allowed: Any, linked: Any, env: dict[str, str] | None = None) -> str | None:
    """First priority channel that is both consented (allowed) and linked for the recipient."""
    a, ln = set(allowed), set(linked)
    return next((c for c in channel_priority(env) if c in a and c in ln), None)


# --- per-stage content mode (port of event_content_plans). Preference only: a visual mode never
# triggers generation here; image/video creation stays behind the executor visual gateway.
CONTENT_STAGES = ("warmup", "event_day_announcement", "post_event_followup")
CONTENT_MODES = ("text", "text_with_image", "text_in_image", "text_with_video")
_MESSAGE_KEY_RE = re.compile(r"[A-Za-z0-9_.:@/-]{1,72}")


def set_content_mode(event_id: str, stage: str, mode: str) -> dict[str, Any]:
    if stage not in CONTENT_STAGES or mode not in CONTENT_MODES or not str(event_id or "").strip():
        raise ValueError("invalid event content mode")
    return {"step": "event_content_mode", "event_id": str(event_id).strip(), "stage": stage, "mode": mode}


def content_plan(st: State, event_id: str) -> dict[str, str]:
    return {stage: st.content_modes.get((event_id, stage), "text") for stage in CONTENT_STAGES}


def event_visual_idempotency_key(*, event_id: str, stage: str, message_key: str) -> str:
    key = str(message_key or "").strip()
    if not _MESSAGE_KEY_RE.fullmatch(key):
        raise ValueError("event visual message key is invalid")
    if stage not in CONTENT_STAGES or not str(event_id or "").strip():
        raise ValueError("invalid event visual scope")
    return f"event:{str(event_id).strip()}:{stage}:{key}:image:v1"


__all__ = [
    "CANON_EVENT_SERIES_FLOW",
    "State",
    "consent",
    "due_messages",
    "followup_allowed",
    "followup_settings",
    "followup_status",
    "mark_attendance",
    "parse_warmup_days",
    "previews",
    "replay",
    "reset_text",
    "safe_warmup_text",
    "segment_of",
    "set_text",
]


# --- event visual assets, media dispatch and stage-visual preparation (ports of event_content_assets,
# event_content_plans, event_followups/event_warmups media helpers). Pure: bytes are stored and sent only by
# the executor; these functions decide and return facts.

ASSET_KINDS = ("image", "video")
_IMAGE_MODES = ("text_with_image", "text_in_image")


class AssetBindError(RuntimeError):
    """Binding failed after the executor stored media; ``facts`` queue the orphan for cleanup."""

    def __init__(self, message: str, facts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.facts = facts


def get_asset(st: State, event_id: str, stage: str, slot_key: str) -> dict[str, Any] | None:
    """Donor get_event_content_asset: None when the optional visual projection has nothing."""
    return st.assets.get((str(event_id), stage, str(slot_key)))


def queue_replaced(reference: str, *, reason: str) -> list[dict[str, Any]]:
    """Donor _queue_replaced: a superseded media reference goes to the bounded cleanup queue (fact)."""
    ref = str(reference or "").strip()
    return [{"step": "media_cleanup_queued", "reference": ref, "reason": reason}] if ref else []


def set_asset_reference(st: State, *, event_id: str, stage: str, slot_key: str, kind: str, media_reference: str,
                        source: str, source_ref: str = "") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if kind not in ASSET_KINDS:
        raise ValueError("event content asset must be image or video")
    if stage not in CONTENT_STAGES or not str(event_id or "").strip() or not str(media_reference or "").strip():
        raise ValueError("invalid event content asset scope")
    if not _MESSAGE_KEY_RE.fullmatch(str(slot_key or "")):
        raise ValueError("event content asset slot is invalid")
    prev = get_asset(st, event_id, stage, slot_key)
    fact = {"step": "event_asset_set", "event_id": str(event_id), "stage": stage, "slot_key": str(slot_key),
            "kind": kind, "media_reference": str(media_reference).strip(), "source": str(source), "source_ref": str(source_ref)}
    if prev and (prev["kind"], prev["media_reference"], prev["source"], prev["source_ref"]) == (
            kind, fact["media_reference"], fact["source"], fact["source_ref"]):
        return prev, []
    facts = [fact]
    if prev is not None and prev["media_reference"] != fact["media_reference"]:
        facts += queue_replaced(prev["media_reference"], reason="superseded_event_content_asset")
    stored = {k: fact[k] for k in ("kind", "media_reference", "source", "source_ref")}
    return {**stored, "revision": (prev["revision"] + 1) if prev else 1}, facts


def store_generated_asset(st: State, *, event_id: str, stage: str, slot_key: str, kind: str, stored_reference: str,
                          source_ref: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Donor store_generated_event_content_asset; the executor stored the bytes and returns ``stored_reference``."""
    if kind not in ASSET_KINDS:
        raise ValueError("generated event content asset must be image or video")
    cur = get_asset(st, event_id, stage, slot_key)
    if cur and cur["source"] == "generated" and cur["source_ref"] == str(source_ref) and cur["kind"] == kind:
        return cur, []
    try:
        return set_asset_reference(st, event_id=event_id, stage=stage, slot_key=slot_key, kind=kind,
                                   media_reference=stored_reference, source="generated", source_ref=source_ref)
    except (ValueError, RuntimeError) as exc:
        raise AssetBindError(str(exc), queue_replaced(stored_reference, reason="failed_event_content_asset_binding")) from exc


def _active_asset(st: State, event_id: str, stage: str, slot_key: str) -> tuple[str, str, int] | None:
    a = get_asset(st, event_id, stage, slot_key)
    if a is None:
        return None
    mode = st.content_modes.get((str(event_id), stage), "text")
    valid = (mode == "text_with_video" and a["kind"] == "video") or (mode in _IMAGE_MODES and a["kind"] == "image")
    return (a["kind"], a["media_reference"], a["revision"]) if valid else None


def active_warmup_visual_asset(st: State, *, event_id: str, slot_key: str) -> tuple[str, str, int] | None:
    return _active_asset(st, event_id, "warmup", slot_key)


def active_followup_visual_asset(st: State, *, event_id: str, slot_key: str) -> tuple[str, str, int] | None:
    return _active_asset(st, event_id, "post_event_followup", slot_key)


def warmup_media_dispatch_key(*, event_id: str, registration_id: str, slot_key: str, message_revision: int,
                              asset_revision: int) -> str:
    return (f"event:{event_id}:registration:{registration_id}:message:warmup-media:v1:"
            f"slot:{str(slot_key).replace(':', '-')}:message-revision:{int(message_revision)}:asset-revision:{int(asset_revision)}")


def followup_media_dispatch_key(*, event_id: str, registration_id: str, stage: int, slot_key: str,
                                message_revision: int, asset_revision: int) -> str:
    return (f"event:{event_id}:registration:{registration_id}:message:post-media:v1:stage:{stage}:"
            f"slot:{str(slot_key).replace(':', '-')}:message-revision:{int(message_revision)}:asset-revision:{int(asset_revision)}")


def materialize_media(st: State, *, key: str, registration_id: str, platform: str, connection_id: str,
                      recipient_kind: str, external_subject: str, asset_kind: str,
                      asset_reference: str) -> tuple[bool, list[dict[str, Any]]]:
    """Idempotent media-dispatch outbox row (donor INSERT ... ON CONFLICT DO NOTHING): True only when newly queued.
    The row is a request; the executor sends it, and only when photo delivery is enabled."""
    if key in st.media_queued:
        return False, []
    return True, [{"step": "event_media_queued", "key": key, "registration_id": registration_id, "platform": platform,
                   "connection_id": connection_id, "recipient_kind": recipient_kind, "external_subject": external_subject,
                   "payload_kind": asset_kind, "payload_ref": asset_reference}]


def resolve_email_target(email_connections: dict[str, Any], *, email_connection_id: str, email: str) -> dict[str, Any] | None:
    """Donor _resolve_email_target: only an active SMTP connection of this business can carry the email."""
    conn = email_connections.get(str(email_connection_id or ""))
    if conn is None or conn.status != "active":
        return None
    return {"platform": "email", "connection_id": conn.id, "recipient_kind": "external_subject",
            "customer_identity_id": None, "external_subject": email}


def followup_subject(segment: str, *, title: str) -> str:
    subjects = {"offer_clicked_unpaid": "После «{t}»", "attended_unpaid": "Продолжение после «{t}»",
                "join_signal_unpaid": "После мероприятия «{t}»", "no_show": "Вы регистрировались: {t}"}
    if segment not in subjects:
        raise ValueError("unsupported event follow-up segment")
    return subjects[segment].format(t=title)


def event_visual_request(*, stage: str, mode: str, event_title: str, message_text: str, session_label: str = "") -> str:
    if mode == "text":
        raise ValueError("text-only mode does not require a visual")
    title, body = " ".join(str(event_title or "").split())[:180], " ".join(str(message_text or "").split())[:900]
    session = " ".join(str(session_label or "").split())[:180]
    if not title or not body:
        raise ValueError("event title and message text are required")
    label = {"warmup": "подготовка", "event_day_announcement": "день события", "post_event_followup": "после события"}[stage]
    ctx = f" Эфир: {session}." if session else ""
    if mode == "text_with_image":
        return (f"Тематическая иллюстрация для этапа «{label}» вебинара «{title}». Смысл сообщения: {body}.{ctx} "
                "Сделай выразительный тематический визуал без читаемого рекламного текста, букв, дат, URL и "
                "интерфейсных элементов; основной текст будет отправлен отдельно.")
    if mode == "text_with_video":
        return (f"Короткое вертикальное видео для этапа «{label}» вебинара «{title}». Смысл сообщения: {body}.{ctx} "
                "Сделай спокойный динамичный ролик с естественным движением и чистым финальным кадром. Не добавляй "
                "читаемый рекламный текст, буквы, даты, URL, интерфейсные элементы, ложные обещания или факты; "
                "основной текст будет отправлен отдельно.")
    return (f"Тематическая карточка для этапа «{label}» вебинара «{title}».{ctx} Размести внутри изображения короткий, "
            f"хорошо читаемый основной текст на русском: «{body}». Сохрани смысл и факты, не добавляй обещаний, цен, "
            "срочности, дат или URL, которых нет в исходном тексте. Текст должен оставаться читаемым на экране телефона.")


def load_goal_visual_brand(brand_facts: list[dict[str, Any]], business_id: str) -> str:
    """Donor _load_goal_visual_brand: the business brand as a prompt context (neutral when none saved)."""
    return brand_discovery.prompt_context(brand_discovery.load_brand(brand_facts, business_id))


def freeze_stage_visual_payload(*, request: str, kind: str, brand_context: str, country_code: str,
                                binding: dict[str, str]) -> str:
    """Donor _freeze_business_visual_payload (event binding form): deterministic frozen brief."""
    return visual_creatives.freeze_payload(request=request, kind=kind, brand_context=brand_context,
                                           country_code=country_code, binding=binding)


def prepare_stage_visual(st: State, gens: Any, member: str, *, business_id: str, brand_facts: list[dict[str, Any]],
                         event_id: str, stage: str, message_key: str, event_title: str, message_text: str,
                         session_label: str = "", country_code: str = "", now_ms: int
                         ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Donor prepare_event_stage_visual: freeze the visual for one stage message and prepare ONE receipt.
    Returns None for text-only stages. Nothing is generated or paid here; consent + the executor do that."""
    mode = content_plan(st, event_id)[stage]
    if mode == "text":
        return None, []
    request = event_visual_request(stage=stage, mode=mode, event_title=event_title, message_text=message_text,
                                   session_label=session_label)
    brand_context = load_goal_visual_brand(brand_facts, business_id)
    kind = "video" if mode == "text_with_video" else "image"
    key = event_visual_idempotency_key(event_id=event_id, stage=stage, message_key=message_key)
    payload = freeze_stage_visual_payload(
        request=request, kind=kind, brand_context=brand_context, country_code=country_code,
        binding={"type": "event_content", "event_id": str(event_id), "stage": stage, "slot_key": message_key, "kind": kind})
    receipt, facts = visual_creatives.gen_prepare(gens, member, request_text=request, brand_context=brand_context,
                                                  country_code=country_code, provider_payload_json=payload,
                                                  now_ms=now_ms, business_id=business_id)
    return {"event_id": str(event_id), "stage": stage, "mode": mode, "receipt_id": receipt.id, "request_text": request,
            "idempotency_key": key, "prepared_for_requested_visual": receipt.request_text == request}, facts
