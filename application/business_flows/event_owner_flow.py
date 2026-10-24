"""Owner flow: create/publish single- and multi-session online events (port of donor event_owner_flow).

Composes ``public_events`` (create/publish facts) with ``pub_event_sessions`` facts; picks the SMTP
notification connection from connection rows (selection only — nothing is sent here).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from application.business_flows import public_events as pe
from application.business_flows.event_wizard import normalize_session_join_url

MAX_SESSIONS = 31


@dataclass(frozen=True)
class SessionSpec:
    starts_at: datetime
    ends_at: datetime | None = None
    join_url: str | None = None
    provider: str | None = None


def notification_connection(connections: list[dict[str, Any]], *, requested: str | None, enabled: bool) -> str | None:
    if not enabled:
        return None
    rows = sorted((c for c in connections if c.get("platform") == "email" and c.get("type") == "email_smtp"
                   and c.get("status") == "active"), key=lambda c: (str(c.get("created_at", "")), str(c["id"])))
    if requested:
        hit = [c for c in rows if str(c["id"]) == str(requested)]
        if len(hit) != 1:
            raise ValueError("selected SMTP notification connection is not active")
        return str(hit[0]["id"])
    if len(rows) > 1:
        raise ValueError("multiple active SMTP connections require explicit selection")
    return str(rows[0]["id"]) if rows else None


def _session(s: SessionSpec) -> dict[str, Any]:
    join = normalize_session_join_url(s.join_url)
    start = pe._dt(s.starts_at)
    end = pe._dt(s.ends_at) if s.ends_at else None
    if end and end <= start:
        raise ValueError("session must end after it starts")
    return {"starts_at": start.isoformat(), "ends_at": end.isoformat() if end else None, "join_url": join,
            "provider_key": pe.provider_key(s.provider, join_url=join)}


def sessions_of(payloads: list[dict[str, Any]], event_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in payloads:
        if p.get("step") == "pub_event_sessions" and p.get("event_id") == event_id:
            out = list(p["sessions"])
    return out


def _sessions_fact(event_id: str, sessions: list[dict[str, Any]]) -> dict[str, Any]:
    if not sessions:
        raise ValueError("event must have at least one session")
    if len(sessions) > MAX_SESSIONS:
        raise ValueError("event has too many sessions")
    return {"step": "pub_event_sessions", "event_id": event_id, "sessions": sorted(sessions, key=lambda s: s["starts_at"])}


def _created(fact: dict[str, Any], *, notify: str | None) -> dict[str, Any]:
    return {**fact, "notification_connection_id": notify}


def create_and_publish(*, title: str, starts_at: datetime, timezone_name: str, now: datetime,
                       connections: list[dict[str, Any]], notify_requested: str | None = None,
                       notify: bool = True, **kw: Any) -> list[dict[str, Any]]:
    created = _created(pe.create_event(title=title, starts_at=starts_at, timezone_name=timezone_name, now=now, **kw),
                       notify=notification_connection(connections, requested=notify_requested, enabled=notify))
    return [created, pe.publish(pe.replay([created]), created["event_id"], now=now)]


def create_draft(*, title: str, timezone_name: str, sessions: list[SessionSpec], now: datetime,
                 connections: list[dict[str, Any]], notify_requested: str | None = None, notify: bool = True,
                 **kw: Any) -> list[dict[str, Any]]:
    if not sessions:
        raise ValueError("event must have at least one session")
    specs = [_session(s) for s in sessions]
    first = sessions[0]
    created = _created(pe.create_event(title=title, starts_at=first.starts_at, timezone_name=timezone_name,
                                       join_url=first.join_url, provider=first.provider, now=now, **kw),
                       notify=notification_connection(connections, requested=notify_requested, enabled=notify))
    return [created, _sessions_fact(created["event_id"], specs)]


def append_session(payloads: list[dict[str, Any]], event_id: str, session: SessionSpec) -> dict[str, Any]:
    ev = pe.replay(payloads).events.get(event_id)
    if ev is None or ev.status != "draft":
        raise pe.EventUnavailable("event draft is no longer editable")
    return _sessions_fact(event_id, [*sessions_of(payloads, event_id), _session(session)])


def publish_draft(payloads: list[dict[str, Any]], event_id: str, *, now: datetime) -> dict[str, Any]:
    return pe.publish(pe.replay(payloads), event_id, now=now)


def create_and_publish_multisession(*, now: datetime, **kw: Any) -> list[dict[str, Any]]:
    f = create_draft(now=now, **kw)
    return [*f, publish_draft(f, f[0]["event_id"], now=now)]


def join_ready(payloads: list[dict[str, Any]], event_id: str) -> bool:
    ss = sessions_of(payloads, event_id)
    ev = pe.replay(payloads).events.get(event_id)
    return all(s["join_url"] for s in ss) if ss else bool(ev and ev.join_url)


def registration_url(public_base_url: str, slug: str) -> str:
    base = normalize_session_join_url(public_base_url)
    if not base:
        raise ValueError("public_base_url required")
    return f"{base.rstrip('/')}/e/{slug}"


# --- sessions (port of donor event_sessions) ---


def configure_sessions(payloads: list[dict[str, Any]], event_id: str, sessions: list[SessionSpec], *, now: datetime,
                       reschedule_notifications: bool = False) -> dict[str, Any]:
    if event_id not in pe.replay(payloads).events:
        raise ValueError("event_not_found")
    if any(pe._dt(s.starts_at) <= pe._dt(now) for s in sessions):
        raise ValueError("event session must start in the future")
    fact = _sessions_fact(event_id, [_session(s) for s in sessions])
    return {**fact, "reschedule_notifications": bool(reschedule_notifications)}


def warmup_window(sessions: list[dict[str, Any]], *, timezone_name: str, now: datetime) -> int:
    """Max warmup days = calendar days (event tz) until the first session."""
    if not sessions:
        raise ValueError("event sessions are required")
    from zoneinfo import ZoneInfo

    z = ZoneInfo(timezone_name)
    first = pe._dt(sessions[0]["starts_at"]).astimezone(z).date()
    return max((first - pe._dt(now).astimezone(z).date()).days, 0)


def validate_warmup_days(requested: object, *, max_days: int) -> int:
    if isinstance(requested, bool) or not isinstance(requested, int):
        raise ValueError("warmup days must be an integer")
    if requested < 0:
        raise ValueError("warmup days must not be negative")
    if requested > max_days:
        raise ValueError("warmup days exceed the time remaining before the event")
    return requested


def select_for_join(sessions: list[dict[str, Any]], *, position: int | None = None, now: datetime,
                    default_hours: int = 2) -> dict[str, Any]:
    """Exact position (1-based) for reminder links; otherwise current/next session, else the last."""
    if not sessions:
        raise ValueError("event sessions are required")
    if position is not None:
        if isinstance(position, bool) or not isinstance(position, int) or position < 1:
            raise ValueError("position must be a positive integer")
        if position > len(sessions):
            raise LookupError("event session was not found")
        return sessions[position - 1]
    from datetime import timedelta

    cur = pe._dt(now)
    for s in sessions:
        end = pe._dt(s["ends_at"]) if s.get("ends_at") else pe._dt(s["starts_at"]) + timedelta(hours=default_hours)
        if cur < end:
            return s
    return sessions[-1]


def set_session_join(payloads: list[dict[str, Any]], event_id: str, position: int, join_url: str,
                     provider: str | None = None) -> dict[str, Any]:
    ss = sessions_of(payloads, event_id)
    if not 1 <= position <= len(ss):
        raise LookupError("event session was not found")
    join = normalize_session_join_url(join_url)
    if not join:
        raise ValueError("join_url required")
    ss[position - 1] = {**ss[position - 1], "join_url": join, "provider_key": pe.provider_key(provider, join_url=join)}
    return _sessions_fact(event_id, ss)


def live_snapshot(payloads: list[dict[str, Any]], slug: str) -> dict[str, Any]:
    """Owner's exact room links for every session (donor cockpit_events.resolve_event_live_snapshot)."""
    ev = pe.by_slug(pe.replay(payloads), slug)
    zone = ZoneInfo(ev.timezone)
    ss = sessions_of(payloads, ev.event_id) or [{"starts_at": ev.starts_at, "join_url": ev.join_url,
                                                 "provider_key": ev.provider_key}]
    rows = [{"position": i, "local_start": pe._dt(s["starts_at"]).astimezone(zone).strftime("%d.%m.%Y %H:%M"),
             "provider_key": s.get("provider_key") or "pending", "join_url": s.get("join_url"),
             "join_ready": bool(s.get("join_url"))} for i, s in enumerate(ss, 1)]
    return {"event_id": ev.event_id, "title": ev.title, "status": ev.status, "timezone": ev.timezone, "sessions": rows}


def live_text(snap: dict[str, Any]) -> str:
    rows = [f"{s['position']}. {s['local_start']} · {s['provider_key']} · "
            + (s["join_url"] if s["join_ready"] else "ссылка не задана") for s in snap["sessions"]]
    return f"🔴 {snap['title']} ({snap['status']}, {snap['timezone']})\n" + "\n".join(rows)
