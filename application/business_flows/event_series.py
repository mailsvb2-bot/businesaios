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


def replay(payloads: list[dict[str, Any]]) -> State:
    st = State()
    for p in payloads:
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
