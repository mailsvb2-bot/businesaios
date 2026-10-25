"""Customer-bot gateway domain (pure): routes, admission, actor/text extraction.

Port of the donor ``application/domain bot_gateway`` + the pure helpers of ``runtime/bot_gateway``:
routes come only from COMPLETED bot_provisioning items (vault/env credential refs, never tokens),
admission dedupes ``update_id`` per bot and enforces payload / rate / queue limits.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from application.business_flows import bot_provisioning as botprov

SESSION_SOURCE = "customer_bot_update"


def _int(env: Mapping[str, str], name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(str(env.get(name, default)).strip())
    except (TypeError, ValueError):
        return default
    return value if lo <= value <= hi else default


def _bool(env: Mapping[str, str], name: str) -> bool:
    return str(env.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    enabled: bool = False
    per_minute_limit: int = 120
    queue_limit: int = 1000
    max_payload_bytes: int = 262_144
    max_attempts: int = 5
    poll_limit: int = 100


def gateway_config(env: Mapping[str, str]) -> GatewayConfig:
    """Flag-gated (CUSTOMER_BOT_GATEWAY_ENABLED, default off); bounded like the donor runtime config."""
    p = "CUSTOMER_BOT_GATEWAY_"
    return GatewayConfig(
        enabled=_bool(env, p + "ENABLED"),
        per_minute_limit=_int(env, p + "PER_BOT_PER_MINUTE", 120, 1, 10_000),
        queue_limit=_int(env, p + "PER_BOT_QUEUE_LIMIT", 1000, 1, 100_000),
        max_payload_bytes=_int(env, p + "MAX_PAYLOAD_BYTES", 262_144, 1024, 1_048_576),
        max_attempts=_int(env, p + "MAX_ATTEMPTS", 5, 1, 20),
    )


@dataclass(frozen=True, slots=True)
class Route:
    tenant_id: str
    request_id: str
    external_bot_id: str
    username: str
    credential_ref: str
    owner_user_id: str = ""
    business: tuple[tuple[str, Any], ...] = ()  # non-secret per-business policy context (see business_context)


def business_context(catalog: Any) -> tuple[tuple[str, Any], ...]:
    """Public business facts the customer-bot policy may show: activity, live offerings, timezone."""
    offerings = tuple(
        o.title[:80] for o in sorted(catalog.offerings.values(), key=lambda o: o.offering_id) if not o.archived
    )[:5]
    return (("activity", str(catalog.activity or "")[:300]), ("offerings", offerings),
            ("timezone", str(catalog.timezone or "Europe/Moscow")))  # fmt: skip


def with_business(routes: list[Route], context: tuple[tuple[str, Any], ...]) -> list[Route]:
    return [replace(r, business=context) for r in routes]


def active_routes(state: dict[str, botprov.Provisioning], *, tenant_id: str) -> list[Route]:
    """Only COMPLETED bots with a credential reference poll; DISABLED/REVOKED stop immediately."""
    return [
        Route(tenant_id, i.request_id, i.external_bot_id, i.username, i.credential_ref, i.user_id)
        for i in sorted(state.values(), key=lambda i: i.request_id)
        if i.status is botprov.ProvisioningStatus.COMPLETED and i.credential_ref and i.external_bot_id
    ]


def resolve_route(routes: list[Route], *, external_bot_id: int | str) -> Route | None:
    """Current route for a Telegram bot id; None once the bot is no longer COMPLETED."""
    wanted = str(external_bot_id).strip()
    return next((r for r in routes if r.external_bot_id == wanted), None)


@dataclass
class Admission:
    """In-process admission: per-bot update_id dedupe, sliding-minute rate, bounded queue, payload size."""

    config: GatewayConfig
    _seen: dict[tuple[str, str], set[int]] = field(default_factory=dict)
    _times: dict[tuple[str, str], deque] = field(default_factory=dict)
    _queued: dict[tuple[str, str], int] = field(default_factory=dict)

    def admit(self, route: Route, payload: Mapping[str, Any], *, now_s: float) -> str:
        uid = payload.get("update_id")
        if isinstance(uid, bool) or not isinstance(uid, int):
            return "rejected:update_id_required"
        scope = (route.tenant_id, route.external_bot_id)
        if not all(isinstance(v, str) and v.strip() for v in scope):
            return "rejected:route_scope_required"
        seen = self._seen.setdefault(scope, set())
        if uid in seen:
            return "duplicate"
        try:
            payload_size = len(json.dumps(payload, ensure_ascii=False).encode())
        except (TypeError, ValueError, OverflowError, RecursionError):
            return "rejected:invalid_payload"
        if payload_size > self.config.max_payload_bytes:
            return "rejected:payload_too_large"
        times = self._times.setdefault(scope, deque())
        while times and now_s - times[0] >= 60:
            times.popleft()
        if len(times) >= self.config.per_minute_limit:
            return "rejected:rate_limited"
        if self._queued.get(scope, 0) >= self.config.queue_limit:
            return "rejected:queue_full"
        seen.add(uid)
        if len(seen) > 4 * self.config.queue_limit:  # bounded memory: keep the newest ids
            for old in sorted(seen)[: len(seen) // 2]:
                seen.discard(old)
        times.append(now_s)
        self._queued[scope] = self._queued.get(scope, 0) + 1
        return "admitted"

    def done(self, route: Route) -> None:
        scope = (route.tenant_id, route.external_bot_id)
        self._queued[scope] = max(0, self._queued.get(route.external_bot_id, 0) - 1)


def message_text(payload: Mapping[str, Any]) -> str | None:
    for key in ("message", "edited_message"):
        candidate = payload.get(key)
        if isinstance(candidate, Mapping):
            text = str(candidate.get("text") or candidate.get("caption") or "").strip()
            if text:
                return text
    return None


def telegram_actor(payload: Mapping[str, Any]) -> tuple[int, str | None, str | None] | None:
    actor: Any = None
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        candidate = payload.get(key)
        if isinstance(candidate, Mapping) and isinstance(candidate.get("from"), Mapping):
            actor = candidate["from"]
            break
    if actor is None and isinstance(payload.get("callback_query"), Mapping):
        actor = payload["callback_query"].get("from")
    if not isinstance(actor, Mapping):
        return None
    raw_id = actor.get("id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
        return None
    name = " ".join(p for p in (str(actor.get("first_name") or "").strip(), str(actor.get("last_name") or "").strip()) if p)
    username = actor.get("username")
    return raw_id, None if username is None else str(username), name or None


def safe_error_code(exc: BaseException) -> str:
    """Class-derived code only: exception messages may carry secret-adjacent text and are never surfaced."""
    name = type(exc).__name__
    code = "".join(("_" + c.lower()) if c.isupper() else c for c in name if c.isalnum() or c == "_").strip("_")
    return (code or "gateway_processing_failed")[:120]


__all__ = [
    "SESSION_SOURCE",
    "Admission",
    "GatewayConfig",
    "Route",
    "active_routes",
    "business_context",
    "gateway_config",
    "message_text",
    "resolve_route",
    "safe_error_code",
    "telegram_actor",
    "with_business",
]
