"""Extra customer-timeline sources (port of ClientPlatform customer_timeline helpers).

Pure projections of already-recorded rows/facts into ``customer_timeline.Entry``: sales
events, signed business-outcome money and external-product observations, plus the
role gates that hide outcome/attribution entries. Nothing is invented: rows that do not
carry a canonical time or the required provenance are skipped or rejected.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from application.business_flows.customer_timeline import Entry

CANON_CUSTOMER_TIMELINE_SOURCES = True
_LEDGER_ROLES = frozenset({"owner", "administrator", "manager"})
STAGE_LABELS = {
    "new": "Новое обращение", "contacted": "Связались с клиентом", "qualified": "Потребность подтверждена",
    "checkout": "Переход к оплате", "won": "Продажа завершена", "lost": "Обращение закрыто без продажи",
}
OUTCOME_LABELS = {
    "lead_created": "Появился лид", "lead_qualified": "Лид квалифицирован", "booking_created": "Создана запись",
    "booking_confirmed": "Запись подтверждена", "booking_completed": "Запись завершена",
    "order_paid": "Получена оплата", "customer_reactivated": "Клиент вернулся",
    "refund_recorded": "Оформлен возврат", "outcome_correction": "Результат скорректирован",
    "outcome_reversal": "Результат отменён",
}
_OBS_SCHEMAS = frozenset({"2026-09-20.v1", "2026-09-20.v2"})
_OBS_QUALITY = {"source_asserted": "сообщено источником", "source_verified": "проверено источником",
                "derived": "вывод источника"}
_SALES_VISIBLE = frozenset({"stage_changed", "next_action_changed", "note_added", "followup_scheduled",
                            "followup_opt_out"})


class TimelineInvariantViolation(RuntimeError):
    """Stored canonical facts cannot be projected without inventing chronology."""


def parse_timestamp(value: object, *, field: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise TimelineInvariantViolation(f"{field} is missing")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise TimelineInvariantViolation(f"{field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise TimelineInvariantViolation(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def payload(raw: object) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        value = json.loads(str(raw or "{}"))
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def bounded(value: object, *, limit: int = 240) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M UTC")


def sales_event_entry(row: Mapping[str, Any]) -> Entry | None:
    event_type = str(row.get("event_type") or "").strip()
    if event_type not in _SALES_VISIBLE:
        return None
    p = payload(row.get("payload_json", row.get("payload")))
    at = parse_timestamp(row.get("occurred_at"), field="sales occurred_at")
    detail: str | None = None
    if event_type == "stage_changed":
        title = STAGE_LABELS.get(str(p.get("to_stage") or "").strip(), "Этап обращения изменён")
    elif event_type == "next_action_changed":
        title, detail = "Обновлён следующий шаг", bounded(p.get("next_action"))
    elif event_type == "note_added":
        title, detail = "Добавлена заметка", bounded(p.get("note"))
    elif event_type == "followup_scheduled":
        title = "Запланирован следующий контакт"
        if p.get("scheduled_at"):
            detail = f"Запланировано на {p['scheduled_at']}"
    else:
        title = "Клиент попросил не писать"
    return Entry(_ms(at), f"sales:{event_type}", title, detail or "")


def direct_signed_money(event: Mapping[str, Any]) -> tuple[int, str] | None:
    amount, currency = event.get("amount_minor"), event.get("currency")
    if amount is None or currency is None:
        return None
    kind = str(event.get("outcome_type") or "")
    if kind == "order_paid":
        if int(amount) < 0:
            raise TimelineInvariantViolation("order_paid outcome contains a negative amount")
        return int(amount), str(currency)
    if kind in {"refund_recorded", "outcome_reversal"}:
        return -abs(int(amount)), str(currency)
    return int(amount), str(currency)


def outcome_money(event: Mapping[str, Any], lookup: Callable[[str], Mapping[str, Any] | None]) -> tuple[int, str] | None:
    """Signed money; a moneyless reversal inherits the negated money of the outcome it reverses."""
    direct = direct_signed_money(event)
    if direct is not None:
        return direct
    if event.get("outcome_type") != "outcome_reversal" or event.get("source_type") != "outcome_event":
        return None
    ref = lookup(str(event.get("source_id") or ""))
    money = None if ref is None else direct_signed_money(ref)
    return None if money is None else (-money[0], money[1])


def outcome_entry(event: Mapping[str, Any], lookup: Callable[[str], Mapping[str, Any] | None]) -> Entry:
    kind = str(event.get("outcome_type") or "")
    at = parse_timestamp(event.get("occurred_at"), field="outcome occurred_at")
    money = outcome_money(event, lookup)
    detail = "" if money is None else f"{money[0] / 100:.2f} {money[1].upper()}"
    return Entry(_ms(at), f"outcome:{kind}", OUTCOME_LABELS[kind], detail)


def external_observation_entry(row: Mapping[str, Any], *, now: datetime) -> Entry | None:
    md = payload(row.get("metadata_json", row.get("metadata")))
    if md.get("external_observation_schema") not in _OBS_SCHEMAS:
        return None
    kind = str(md.get("external_observation_kind") or "").strip()
    label = bounded(md.get("external_observation_label"), limit=160)
    prov = bounded(md.get("external_observation_provenance_ref"), limit=300)
    quality = _OBS_QUALITY.get(str(md.get("external_observation_quality") or "").strip())
    if not kind or label is None or prov is None or quality is None:
        return None
    observed = parse_timestamp(md.get("external_observation_observed_at"), field="external observation observed_at")
    raw_lim = md.get("external_observation_limitations") or []
    if not isinstance(raw_lim, list):
        return None
    lims = tuple(t for i in raw_lim[:8] if isinstance(i, str) and (t := bounded(i, limit=200)))
    connector = bounded(row.get("connector_name"), limit=160)
    if connector is None:
        return None
    rev = None if row.get("observation_revision") is None else int(row["observation_revision"])
    state = None if row.get("observation_state") is None else str(row["observation_state"])
    fresh_raw = row.get("observation_fresh_until")
    fresh = None if fresh_raw is None else parse_timestamp(fresh_raw, field="external observation fresh_until")
    if state == "retracted":
        freshness = "отозвано источником"
    elif fresh is None:
        freshness = "свежесть неизвестна"
    elif fresh < now:
        freshness = f"возможно устарело после {_fmt(fresh)}"
    else:
        freshness = f"актуально до {_fmt(fresh)}"
    parts = [f"Источник: {connector}", quality, f"наблюдалось {_fmt(observed)}", freshness]
    if rev is not None:
        parts.append(f"ревизия {rev}")
    if lims:
        parts.append("ограничения: " + "; ".join(lims))
    title = "Внешнее наблюдение отозвано" if state == "retracted" else label
    return Entry(_ms(observed), f"external_observation:{kind}", title, " · ".join(parts))


def can_view_outcomes(role: str) -> bool:
    return str(role or "") in _LEDGER_ROLES


def can_view_attribution(role: str) -> bool:
    return str(role or "") in _LEDGER_ROLES


__all__ = [
    "CANON_CUSTOMER_TIMELINE_SOURCES", "TimelineInvariantViolation", "bounded", "can_view_attribution",
    "can_view_outcomes", "direct_signed_money", "external_observation_entry", "outcome_entry", "outcome_money",
    "parse_timestamp", "payload", "sales_event_entry",
]
