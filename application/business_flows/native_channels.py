"""VK / MAX native channel onboarding state machine (donor ``native_messenger_onboarding``).

Pure: provider I/O is an injected client, durable state is ``business_admin@v1`` facts
(``nm_lease``, ``nm_active``, ``nm_disabled``). Facts never carry provider tokens or webhook
secrets: tokens are ``env:``/``vault:`` references and the webhook secret is derived from a
server key per route, so a retried provisioning keeps the same secret (donor reused the stored one).
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Protocol
from urllib.parse import urlsplit

PLATFORMS = ("vk", "max")
LEASE_MS = 120_000
_REF = re.compile(r"^(env|vault):[A-Za-z_][A-Za-z0-9_]{0,63}$")


class Provider(Protocol):
    def verify_community(self, group_id: str) -> dict[str, Any]: ...
    def get_callback_confirmation_code(self, group_id: str) -> str: ...
    def ensure_callback_server(self, *, group_id: str, url: str, secret: str) -> None: ...
    def get_me(self) -> dict[str, Any]: ...
    def ensure_webhook_subscription(self, *, url: str, secret: str) -> None: ...


@dataclass(frozen=True, slots=True)
class Route:
    route_id: str
    platform: str
    external_id: str
    status: str = "provisioning"
    token_ref: str = ""
    confirmation_code: str | None = None
    display_name: str | None = None
    username: str | None = None
    lease_owner: str = ""
    lease_until_ms: int = 0


def route_id(platform: str, external_id: str) -> str:
    return "nm_" + hashlib.sha256(f"{platform}:{external_id}".encode()).hexdigest()[:16]


def replay(facts: list[dict[str, Any]]) -> dict[str, Route]:
    out: dict[str, Route] = {}
    for f in facts:
        step, rid = f.get("step"), str(f.get("route_id") or "")
        if step == "nm_lease":
            r = out.get(rid) or Route(rid, f["platform"], f["external_id"])
            out[rid] = replace(r, lease_owner=f["owner"], lease_until_ms=int(f["until_ms"]))
        elif rid in out and step == "nm_active":
            keep = ("token_ref", "confirmation_code", "display_name", "username")
            out[rid] = replace(
                out[rid], status="active", lease_owner="", lease_until_ms=0, **{k: f.get(k) for k in keep}
            )
        elif rid in out and step == "nm_disabled":
            out[rid] = replace(out[rid], status="disabled", lease_owner="", lease_until_ms=0)
    return out


def public_base_url(value: str) -> str:
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("messenger public base URL must use HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("messenger public base URL is invalid")
    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise ValueError("messenger public base URL is invalid") from exc
    if explicit_port is not None or parsed.path not in {"", "/"}:
        raise ValueError("messenger public base URL must be an HTTPS origin")
    return normalized


def webhook_secret(server_key: str, rid: str) -> str:
    if len(str(server_key or "").encode()) < 32:
        raise ValueError("webhook server key must be at least 32 bytes")
    return hmac.new(server_key.encode(), f"nm-webhook:{rid}".encode(), hashlib.sha256).hexdigest()


PROVIDER_KEYS = {"vk": "vk_messaging", "max": "max_messaging"}


def webhook_url(base_url: str, platform: str, *, tenant_id: str, business_id: str) -> str:
    """Existing generic ingress (adapters/api/fastapi/provider_webhook_routes.py) owns VK/MAX inbound."""
    return f"{base_url}/providers/webhook/{tenant_id}/{business_id}/{PROVIDER_KEYS[platform]}"


def acquire_lease(
    routes: dict[str, Route], *, platform: str, external_id: str, owner: str, now_ms: int
) -> dict[str, Any]:
    rid = route_id(platform, external_id)
    r = routes.get(rid)
    if r and r.lease_owner and r.lease_owner != owner and r.lease_until_ms > now_ms:
        raise ValueError("подключение этого канала уже выполняется")
    return {
        "step": "nm_lease",
        "route_id": rid,
        "platform": platform,
        "external_id": external_id,
        "owner": owner,
        "until_ms": now_ms + LEASE_MS,
    }


def _disabled(rid: str, reason: str) -> dict[str, Any]:
    return {"step": "nm_disabled", "route_id": rid, "reason": reason}


def _provision(
    platform, ext, *, provider, token_ref, base_url, server_key, routes, owner, now_ms, confirm, register, extra, scope
):
    lease = acquire_lease(routes, platform=platform, external_id=ext, owner=owner, now_ms=now_ms)
    rid = lease["route_id"]
    url, secret = webhook_url(base_url, platform, **scope), webhook_secret(server_key, rid)
    try:
        register(url, secret)
    except (OSError, ValueError, RuntimeError) as exc:
        return [lease, _disabled(rid, f"provider_failure:{type(exc).__name__}")], None
    active = {"step": "nm_active", "route_id": rid, "token_ref": token_ref, "confirmation_code": confirm, **extra}
    return [lease, active], url


def provision_vk(*, group_id: str | int, token_ref: str, provider: Provider, base_url: str, server_key: str,
                 routes: dict[str, Route], owner: str, now_ms: int,
                 tenant_id: str, business_id: str) -> tuple[list[dict[str, Any]], str | None]:  # fmt: skip
    base = public_base_url(base_url)
    if not _REF.match(str(token_ref or "")):
        raise ValueError("токен VK передаётся только ссылкой env:NAME или vault:NAME")
    gid = str(group_id or "").strip()
    if not gid.isdigit() or int(gid) <= 0:
        raise ValueError("VK group id must be a positive integer")
    group = provider.verify_community(gid)
    code = provider.get_callback_confirmation_code(gid)
    reg = lambda url, secret: provider.ensure_callback_server(group_id=gid, url=url, secret=secret)  # noqa: E731
    extra = {"display_name": str(group.get("name") or "").strip() or None, "username": None}
    return _provision("vk", gid, provider=provider, token_ref=token_ref, base_url=base, server_key=server_key,
                      routes=routes, owner=owner, now_ms=now_ms, confirm=code, register=reg, extra=extra,
                      scope={"tenant_id": tenant_id, "business_id": business_id})  # fmt: skip


def provision_max(*, token_ref: str, provider: Provider, base_url: str, server_key: str,
                  routes: dict[str, Route], owner: str, now_ms: int,
                 tenant_id: str, business_id: str) -> tuple[list[dict[str, Any]], str | None]:  # fmt: skip
    base = public_base_url(base_url)
    if not _REF.match(str(token_ref or "")):
        raise ValueError("токен MAX передаётся только ссылкой env:NAME или vault:NAME")
    me = provider.get_me()
    ext = str(me.get("user_id") or "").strip()
    if not ext:
        raise ValueError("MAX bot identity is missing user_id")
    reg = lambda url, secret: provider.ensure_webhook_subscription(url=url, secret=secret)  # noqa: E731
    name = str(me.get("first_name") or me.get("name") or "").strip() or None
    extra = {"display_name": name, "username": str(me.get("username") or "").strip() or None}
    return _provision("max", ext, provider=provider, token_ref=token_ref, base_url=base, server_key=server_key,
                      routes=routes, owner=owner, now_ms=now_ms, confirm=None, register=reg, extra=extra,
                      scope={"tenant_id": tenant_id, "business_id": business_id})  # fmt: skip


def disable(routes: dict[str, Route], rid: str) -> dict[str, Any]:
    if rid not in routes:
        raise ValueError("канал не найден")
    return _disabled(rid, "owner")


# --- email SMTP connections (donor email_connections): pending until the provider accepts the credentials ---
# Donor stored the SMTP password encrypted in its own vault; here SMTP material is only ``env:``/``vault:``
# references (never a literal) and the SMTP probe is an injected, executor-owned callable.

_HOST = re.compile(r"[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?")
_EMAIL = re.compile(r"[^@\s<>]{1,64}@[a-z0-9.-]{1,253}\.[a-z]{2,24}")
SMTP_SECURITY = ("ssl", "starttls")


@dataclass(frozen=True, slots=True)
class EmailConn:
    id: str
    sender_email: str
    host: str
    port: int
    username_ref: str
    password_ref: str
    security: str
    sender_name: str = ""
    status: str = "pending"  # pending | active


def email_connection_id(sender_email: str) -> str:
    return "ec_" + hashlib.sha256(f"email_smtp:{sender_email}".encode()).hexdigest()[:16]


def normalize_email(value: object) -> str:
    email = str(value or "").strip().lower()
    if not _EMAIL.fullmatch(email) or ".." in email:
        raise ValueError("email address is invalid")
    return email


def email_replay(facts: list[dict[str, Any]]) -> dict[str, EmailConn]:
    out: dict[str, EmailConn] = {}
    for f in facts:
        cid = str(f.get("id") or "")
        if f.get("step") == "email_conn_pending":
            out[cid] = EmailConn(**{k: f[k] for k in EmailConn.__dataclass_fields__ if k in f and k != "status"})
        elif f.get("step") == "email_conn_active" and cid in out:
            out[cid] = replace(out[cid], status="active")
    return out


def provision_email_smtp(
    *,
    sender_email: str,
    smtp_host: str,
    smtp_port: int,
    username_ref: str,
    password_ref: str,
    security: str = "ssl",
    sender_name: str = "",
) -> tuple[EmailConn, list[dict[str, Any]]]:
    """Donor provision_email_smtp_connection: validated, pending, re-verification required."""
    sender = normalize_email(sender_email)
    host = str(smtp_host or "").strip().lower()
    if not _HOST.fullmatch(host) or "." not in host:
        raise ValueError("SMTP host is invalid")
    port = int(smtp_port)
    if not 1 <= port <= 65535:
        raise ValueError("SMTP port is invalid")
    for ref in (username_ref, password_ref):
        if not _REF.match(str(ref or "")):
            raise ValueError("SMTP логин и пароль передаются только ссылкой env:NAME или vault:NAME")
    name = " ".join(str(sender_name or "").split())
    if len(name) > 160:
        raise ValueError("SMTP sender name is too long")
    sec = str(security or "").strip().lower()
    if sec not in SMTP_SECURITY:
        raise ValueError("SMTP security must be ssl or starttls")
    fact = {
        "step": "email_conn_pending",
        "id": email_connection_id(sender),
        "sender_email": sender,
        "host": host,
        "port": port,
        "username_ref": username_ref,
        "password_ref": password_ref,
        "security": sec,
        "sender_name": name,
    }
    return email_replay([fact])[fact["id"]], [fact]


def verify_and_activate_email_smtp(
    conns: dict[str, EmailConn], connection_id: str, probe: Callable[[EmailConn], None]
) -> tuple[EmailConn, list[dict[str, Any]]]:
    """Probe SMTP auth first (injected, executor-owned), then activate exactly that connection."""
    conn = conns.get(str(connection_id))
    if conn is None:
        raise ValueError("email connection was not found in the active business")
    if normalize_email(conn.sender_email) != conn.sender_email:
        raise ValueError("SMTP credential sender does not match the connection account")
    probe(conn)  # raises on rejected credentials: the connection then stays pending
    return replace(conn, status="active"), [{"step": "email_conn_active", "id": conn.id}]


__all__ = ["EmailConn", "email_connection_id", "email_replay", "normalize_email", "provision_email_smtp", "verify_and_activate_email_smtp", "PLATFORMS", "PROVIDER_KEYS", "Provider", "Route", "acquire_lease", "disable", "provision_max", "provision_vk",
           "public_base_url", "replay", "route_id", "webhook_secret", "webhook_url"]  # fmt: skip
