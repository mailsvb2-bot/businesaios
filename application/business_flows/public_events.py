"""Public event lifecycle and registration (port of donor application/events) over
``public_events@v1`` facts.

The lifecycle runs draft -> published -> cancelled. Registration needs consent and is
idempotent per normalized email. A cancelled registration cannot come back. Cancelling an
event or a registration emits ``event_dispatch_cancelled`` so the executor's outbox drops
pending reminders. This module itself sends nothing. Join URLs reuse
``event_wizard.normalize_session_join_url`` (HTTPS only).
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from application.business_flows.event_wizard import normalize_session_join_url
from application.business_flows.projection import stable_id

CONSENT_VERSION = "2026-09-online-event-v2"
KINDS = frozenset({"webinar", "online_event", "workshop", "masterclass"})
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_HOSTS = (
    ("zoom.us", "zoom"),
    ("vk.com", "vk"),
    ("vkvideo.ru", "vk"),
    ("youtube.com", "youtube"),
    ("youtu.be", "youtube"),
    ("rutube.ru", "rutube"),
    ("webinar.ru", "webinar_ru"),
    ("mts-link.ru", "mts_link"),
    ("telemost.yandex.ru", "yandex_telemost"),
)
_ALIASES = {
    "webinar.ru": "webinar_ru",
    "webinar-ru": "webinar_ru",
    "mts-link": "mts_link",
    "mts.link": "mts_link",
    "yandex-telemost": "yandex_telemost",
    "telemost": "yandex_telemost",
    "vk_video": "vk",
    "vk-video": "vk",
}


class EventUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class PubEvent:
    event_id: str
    title: str
    kind: str
    starts_at: str
    timezone: str
    slug: str
    status: str = "draft"
    join_url: str | None = None
    provider_key: str = "pending"
    offer_url: str | None = None

    def accepts_registrations(self, now: datetime) -> bool:
        return self.status == "published" and _dt(self.starts_at) > now

    def local_start_label(self) -> str:
        return _dt(self.starts_at).astimezone(ZoneInfo(self.timezone)).strftime("%d.%m.%Y %H:%M")


@dataclass(frozen=True)
class Registration:
    registration_id: str
    event_id: str
    email_hash: str
    token_hash: str
    name: str
    status: str = "registered"


@dataclass
class Board:
    events: dict[str, PubEvent] = field(default_factory=dict)
    registrations: dict[str, Registration] = field(default_factory=dict)


def _dt(v: str | datetime) -> datetime:
    d = v if isinstance(v, datetime) else datetime.fromisoformat(str(v))
    if d.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return d.astimezone(UTC).replace(microsecond=0)


def _h(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def provider_key(value: object | None, *, join_url: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not join_url and raw in {"", "auto", "pending"}:
        return "pending"
    if raw in {"", "auto"}:
        host = (urlsplit(str(join_url)).hostname or "").lower().rstrip(".")
        return next((k for s, k in _HOSTS if host == s or host.endswith("." + s)), "external")
    key = _ALIASES.get(raw, raw).replace(" ", "_")
    if not _KEY_RE.fullmatch(key):
        raise ValueError("invalid provider_key")
    return key


def replay(payloads: list[dict[str, Any]]) -> Board:
    b = Board()
    for p in payloads:
        s, eid = p.get("step"), str(p.get("event_id") or "")
        ev = b.events.get(eid)
        if s == "pub_event_created" and eid not in b.events:
            b.events[eid] = PubEvent(
                eid,
                p["title"],
                p["kind"],
                p["starts_at"],
                p["timezone"],
                p["slug"],
                join_url=p.get("join_url"),
                provider_key=p["provider_key"],
                offer_url=p.get("offer_url"),
            )
        elif ev and s == "pub_event_status":
            b.events[eid] = replace(ev, status=p["status"])
        elif ev and s == "pub_event_join":
            b.events[eid] = replace(ev, join_url=p["join_url"], provider_key=p["provider_key"])
        elif s == "pub_registration" and p["registration_id"] not in b.registrations:
            b.registrations[p["registration_id"]] = Registration(
                p["registration_id"], eid, p["email_hash"], p["token_hash"], p["name"]
            )
        elif s == "pub_registration_cancelled" and p["registration_id"] in b.registrations:
            r = b.registrations[p["registration_id"]]
            b.registrations[r.registration_id] = replace(r, status="cancelled")
    return b


def create_event(
    *,
    title: str,
    starts_at: datetime,
    timezone_name: str,
    join_url: str | None = None,
    provider: str | None = None,
    kind: str = "webinar",
    offer_url: str | None = None,
    now: datetime,
) -> dict[str, Any]:
    start = _dt(starts_at)
    if start <= _dt(now):
        raise ValueError("event must start in the future")
    kind = str(kind or "").strip().lower()
    if kind not in KINDS:
        raise ValueError("unsupported event kind")
    ZoneInfo(timezone_name)
    t = " ".join(str(title or "").split())[:200]
    if not t:
        raise ValueError("title required")
    join = normalize_session_join_url(join_url)
    offer = normalize_session_join_url(offer_url)
    return {
        "step": "pub_event_created",
        "event_id": stable_id("pev", t, start.isoformat()),
        "title": t,
        "kind": kind,
        "starts_at": start.isoformat(),
        "timezone": timezone_name,
        "slug": secrets.token_urlsafe(24),
        "join_url": join,
        "provider_key": provider_key(provider, join_url=join),
        "offer_url": offer,
        "consent_version": CONSENT_VERSION,
    }


def _event(b: Board, event_id: str) -> PubEvent:
    if event_id not in b.events:
        raise ValueError("event_not_found")
    return b.events[event_id]


def publish(b: Board, event_id: str, *, now: datetime) -> dict[str, Any]:
    ev = _event(b, event_id)
    if _dt(ev.starts_at) <= _dt(now):
        raise EventUnavailable("cannot publish an event that has already started")
    if ev.status != "draft":
        raise EventUnavailable("event_state_conflict")
    return {"step": "pub_event_status", "event_id": ev.event_id, "status": "published"}


def set_join_target(b: Board, event_id: str, join_url: str, provider: str | None = None) -> dict[str, Any]:
    ev, join = _event(b, event_id), normalize_session_join_url(join_url)
    if join is None:
        raise ValueError("join_url required")
    return {
        "step": "pub_event_join",
        "event_id": ev.event_id,
        "join_url": join,
        "provider_key": provider_key(provider, join_url=join),
    }


def cancel(b: Board, event_id: str) -> list[dict[str, Any]]:
    ev = _event(b, event_id)
    if ev.status not in {"draft", "published"}:
        raise EventUnavailable("event cannot be cancelled from its current state")
    regs = [r.registration_id for r in b.registrations.values() if r.event_id == ev.event_id]
    return [
        {"step": "pub_event_status", "event_id": ev.event_id, "status": "cancelled"},
        {
            "step": "event_dispatch_cancelled",
            "event_id": ev.event_id,
            "registration_ids": regs,
            "reason": "event_cancelled",
        },
    ]


def clean_dimension(value: object | None, field: str, maximum: int) -> str | None:
    """Donor event_growth._clean_dimension: acquisition source/campaign as seen on the landing URL."""
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split())
    if not text:
        return None
    if len(text) > maximum:
        raise ValueError(f"{field} is too long")
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError(f"{field} contains control characters")
    return text


def by_slug(b: Board, slug: str) -> PubEvent:
    ev = next((e for e in b.events.values() if e.slug == slug), None)
    if ev is None or ev.status not in {"published", "cancelled"}:
        raise ValueError("event_not_found")
    return ev


def register(
    b: Board, *, slug: str, name: str, email: str, consent: bool, now: datetime,
    source: object | None = None, campaign_ref: object | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """(fact, raw_token). Repeat registration -> (None, None); the token is shown once, only its hash is kept."""
    if consent is not True:
        raise ValueError("consent is required")
    ev = by_slug(b, slug)
    if not ev.accepts_registrations(_dt(now)):
        raise EventUnavailable("registration is closed")
    mail = str(email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", mail):
        raise ValueError("email invalid")
    eh = _h(mail)
    prior = next((r for r in b.registrations.values() if r.event_id == ev.event_id and r.email_hash == eh), None)
    if prior is not None:
        if prior.status == "cancelled":
            raise EventUnavailable("registration is closed")
        return None, None
    token = secrets.token_urlsafe(32)
    return (
        {
            "step": "pub_registration",
            "registration_id": stable_id("preg", ev.event_id, eh),
            "event_id": ev.event_id,
            "email_hash": eh,
            "token_hash": _h(token),
            "name": " ".join(str(name or "").split())[:120],
            "consent_version": CONSENT_VERSION,
            **{k: v for k, v in (("source", clean_dimension(source, "source", 160)),
                                 ("campaign_ref", clean_dimension(campaign_ref, "campaign_ref", 200))) if v},
        },
        token,
    )


def cancel_registration_by_token(b: Board, token: str) -> list[dict[str, Any]]:
    th = _h(str(token or "").strip())
    r = next((r for r in b.registrations.values() if r.token_hash == th and r.status == "registered"), None)
    if r is None:
        raise EventUnavailable("registration is no longer active")
    return [
        {"step": "pub_registration_cancelled", "registration_id": r.registration_id, "event_id": r.event_id},
        {
            "step": "event_dispatch_cancelled",
            "event_id": r.event_id,
            "registration_ids": [r.registration_id],
            "reason": "event_registration_cancelled",
        },
        {"step": "event_commercial_consent_revoked", "registration_id": r.registration_id},
    ]


# --- managed (UCR) conference join planning (port of event_conference_join). Pure: returns the
# ordered idempotent UCR UniversalConference RPC intents; only the executor may run them through
# interfaces.ucr.gateway (disabled unless BUSINESAIOS_UCR_GATEWAY_ENABLED). Join URLs are never stored.
UCR_PROVIDER_KEY = "ucr"
UCR_INTEGRATION_ENV = "BUSINESAIOS_UCR_CONFERENCE_INTEGRATION_ID"
JOIN_TTL_SECONDS = 15 * 60


def ucr_conference_integration_id(env: dict[str, str] | None = None) -> str:
    import os

    from interfaces.ucr.gateway import UcrGatewayConfigurationError
    value = str((os.environ if env is None else env).get(UCR_INTEGRATION_ENV) or "").strip()
    if not value or len(value) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise UcrGatewayConfigurationError("UCR conference integration id is required")
    return value


def ucr_provider_available(env: dict[str, str] | None = None) -> bool:
    from interfaces.ucr.gateway import UcrGatewayConfigurationError, ucr_gateway_config
    try:
        if not ucr_gateway_config(env).enabled:
            return False
        ucr_conference_integration_id(env)
    except UcrGatewayConfigurationError:
        return False
    return True


def is_managed(ev: PubEvent) -> bool:
    return ev.provider_key == UCR_PROVIDER_KEY


def attempt_id(value: str | None) -> str:
    import uuid
    if value is None:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("conference join attempt id is invalid") from exc


def _conf_steps(ev: PubEvent, position: int, owner_member_id: str, who: str, *, tenant_id: str) -> list[dict[str, Any]]:
    if not is_managed(ev):
        raise ValueError("event session is not managed by UCR")
    if ev.status != "published":
        raise ValueError("event is not active")
    eid, pos = ev.event_id, int(position)
    rk = "runtime:" + hashlib.sha256(f"{eid}:{pos}:{who}".encode()).hexdigest()
    s = [("CreateConference", f"conference:{eid}:{pos}", {"external_conference_id": f"bai:event:{eid}:session:{pos}",
                                                         "mode": "webinar"}),
         ("EnsureParticipant", f"owner:{eid}:{pos}", {"external_user_id": f"bai:event-owner:{owner_member_id}",
                                                     "role": "owner"})]
    return [{"method": m, "idempotency_key": k, "tenant_id": tenant_id, "request": r} for m, k, r in s] + [
        {"method": "PrepareConferenceRuntime", "idempotency_key": rk, "tenant_id": tenant_id, "request": {}},
        {"method": "TransitionConference", "idempotency_key": f"waiting:{eid}:{pos}", "tenant_id": tenant_id,
         "request": {"lifecycle": "waiting", "only_if": ["scheduled", None]}},
        {"method": "SetEntryOpen", "idempotency_key": f"entry-open:{eid}:{pos}", "tenant_id": tenant_id,
         "request": {"open": True}}]


def attendee_join_plan(b: Board, ev: PubEvent, registration_id: str, *, position: int, owner_member_id: str,
                       tenant_id: str, join_attempt_id: str | None = None, ttl_seconds: int = JOIN_TTL_SECONDS) -> list[dict[str, Any]]:
    reg = b.registrations.get(registration_id)
    if reg is None or reg.event_id != ev.event_id:
        raise ValueError("event registration does not belong to the selected session")
    if reg.status != "registered":
        raise ValueError("event registration is not active")
    who = f"bai:event-registration:{registration_id}"
    steps = _conf_steps(ev, position, owner_member_id, who, tenant_id=tenant_id)
    steps.insert(2, {"method": "EnsureParticipant", "tenant_id": tenant_id,
                     "idempotency_key": f"participant:{ev.event_id}:{position}:{registration_id}",
                     "request": {"external_user_id": who, "role": "attendee"}})
    att = attempt_id(join_attempt_id)
    return [*steps, {"method": "IssueJoinGrant", "tenant_id": tenant_id, "store_url": False,
                     "idempotency_key": f"join:{ev.event_id}:{position}:{registration_id}:{att}",
                     "request": {"external_user_id": who, "ttl_seconds": int(ttl_seconds)}}]


def owner_join_plan(ev: PubEvent, *, position: int, owner_member_id: str, actor_member_id: str, can_manage: bool,
                    tenant_id: str, join_attempt_id: str | None = None, ttl_seconds: int = JOIN_TTL_SECONDS) -> list[dict[str, Any]]:
    if not can_manage:
        raise PermissionError("actor cannot manage this business")
    owner = actor_member_id == owner_member_id
    who = f"bai:event-owner:{owner_member_id}" if owner else f"bai:event-host:{actor_member_id}"
    steps = _conf_steps(ev, position, owner_member_id, who, tenant_id=tenant_id)
    if not owner:
        steps.insert(2, {"method": "EnsureParticipant", "tenant_id": tenant_id,
                         "idempotency_key": f"host:{ev.event_id}:{position}:{actor_member_id}",
                         "request": {"external_user_id": who, "role": "host"}})
    att = attempt_id(join_attempt_id)
    return [*steps, {"method": "IssueJoinGrant", "tenant_id": tenant_id, "store_url": False,
                     "idempotency_key": f"host-join:{ev.event_id}:{position}:{actor_member_id}:{att}",
                     "request": {"external_user_id": who, "ttl_seconds": int(ttl_seconds)}}]
