"""Owner cockpit event screens (donor native_member_interactions events / conduct / follow-up content).

Pure: lists past bookings awaiting an attendance mark, offers attended / no-show buttons
that produce the same ``attendance`` fact as ``/attendance`` (event_series.mark_attendance),
and shows the series texts preview. Follow-ups are still sent only by the series job.
"""

from __future__ import annotations

from typing import Any

from application.business_flows import event_series as es

CANON_COCKPIT_EVENTS = True
PARENTS = {"ev-conduct": "cpm:events", "ev-texts": "cpm:events"}
MUTATIONS = frozenset({"ev-att"})
_STATUS = {"a": "attended", "n": "no_show"}
LABEL = {"attended": "пришёл", "no_show": "не пришёл"}


def _pending(s: Any) -> list[Any]:
    att = getattr(s.series, "attendance", {}) or {}
    return [
        x
        for x in s.all_slots
        if x.status == "booked" and x.starts_at_ms <= s.now_ms and (x.slot_id, x.customer_id) not in att
    ][::-1]


def screen(action: str, args: tuple[str, ...], s: Any) -> tuple[str, list[list[tuple[str, str]]]]:
    if action == "ev-conduct":
        items = _pending(s)[:5]
        if not items:
            return "✅ Все прошедшие встречи отмечены.", []
        lines = [f"{i}. {s.fmt_slot(x)} · клиент …{x.customer_id[-4:]}" for i, x in enumerate(items, 1)]
        rows = [
            [(f"✅ {i} пришёл", f"cpm:ev-att:{x.slot_id}:a"), (f"🚫 {i} не пришёл", f"cpm:ev-att:{x.slot_id}:n")]
            for i, x in enumerate(items, 1)
        ]
        return "🎤 Отметить посещение\n\n" + "\n".join(lines), rows
    if action == "ev-texts":
        body = "\n".join(es.previews(s.series or es.State())) or "Текстов нет."
        return "✉️ Тексты прогрева и follow-up\n\n" + body[:3500] + "\n\nИзменить: /series", []
    raise ValueError(action)


def mutation(action: str, args: tuple[str, ...], s: Any) -> tuple[str, dict[str, Any]]:
    if action != "ev-att" or len(args) != 2 or args[1] not in _STATUS:
        raise ValueError("attendance mutation")
    slot = next((x for x in s.all_slots if x.slot_id == args[0]), None)
    att = getattr(s.series, "attendance", {}) or {}
    if slot is not None and (slot.slot_id, slot.customer_id) in att:
        return "Посещение уже отмечено.", {}
    change = es.mark_attendance(slot, _STATUS[args[1]], now_ms=s.now_ms)
    return f"✅ Отмечено: {s.fmt_slot(slot)} — {LABEL[change['status']]}", change


__all__ = ["CANON_COCKPIT_EVENTS", "MUTATIONS", "PARENTS", "mutation", "screen"]
