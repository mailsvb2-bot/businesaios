"""Owner flow: create/publish single- and multi-session online events (port of donor event_owner_flow).

Composes ``public_events`` (create/publish facts) with ``pub_event_sessions`` facts; picks the SMTP
notification connection from connection rows (selection only — nothing is sent here).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

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
