from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from contracts.action_budget import ADMIN_ANALYTICS_ROUTES
from contracts.messaging_channels import ALL_CHANNELS
from core.safety.controls.key_registry import SafetyKeyRegistry


@dataclass(frozen=True)
class ActionBudget:
    max_cost: float
    max_actions: int


_VERIFIED_INGRESS: ContextVar[tuple | None] = ContextVar("verified_inbound_reply", default=None)
_PROOF_FIELDS = ("tenant_id", "channel", "user_id", "update_id", "chat_id", "content_sha256", "issued_at", "key_id")


def _execution_owner() -> tuple[int, object | None]:
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return threading.get_ident(), task


@contextmanager
def verified_inbound_reply_scope(*, tenant_id: str, channel: str, user_id: str,
                                 update_id: object, chat_id: str = "", bot_id: str = "primary") -> Iterator[None]:
    bot_scope = str(bot_id or "primary").strip() or "primary"
    token = _VERIFIED_INGRESS.set((str(tenant_id), str(channel), str(user_id), update_id,
                                   str(chat_id), _execution_owner(), bot_scope))
    try:
        yield
    finally:
        _VERIFIED_INGRESS.reset(token)


def _proof_mac(proof: Mapping[str, Any], secret: bytes) -> str:
    material = json.dumps([proof.get(field) for field in _PROOF_FIELDS],
                          separators=(",", ":"), ensure_ascii=False).encode()
    return hmac.new(secret, b"businesaios:inbound-reply:v1:" + material, hashlib.sha256).hexdigest()


def issue_verified_reply(*, tenant_id: str, channel: str, user_id: str,
                         update_id: object, chat_id: str = "", text: str = "",
                         bot_id: str = "primary") -> dict[str, Any] | None:
    bot_scope = str(bot_id or "primary").strip() or "primary"
    expected = (str(tenant_id), str(channel), str(user_id), update_id, str(chat_id), _execution_owner(), bot_scope)
    if _VERIFIED_INGRESS.get() != expected:
        return None
    key = SafetyKeyRegistry().current
    if key.insecure_fallback or not key.active:
        return None
    proof = dict(tenant_id=tenant_id, channel=channel, user_id=user_id, update_id=update_id,
                 chat_id=chat_id, content_sha256=hashlib.sha256(text.encode()).hexdigest(),
                 issued_at=int(time.time()), key_id=key.key_id)
    proof["signature"] = _proof_mac(proof, key.secret)
    return proof


def _telegram_update_key(tenant_id: str, bot_id: str, user_id: str, update_id: int) -> str:
    material = json.dumps([tenant_id, bot_id, user_id, update_id],
                          separators=(",", ":"), ensure_ascii=False).encode()
    return "telegram:" + hashlib.sha256(material).hexdigest()


def issue_verified_update_idempotency_key(*, tenant_id: str, channel: str, user_id: str,
                                          update_id: object, chat_id: str = "",
                                          bot_id: str = "primary") -> str | None:
    if channel != "telegram" or type(update_id) is not int or update_id < 0:
        return None
    bot_scope = str(bot_id or "primary").strip() or "primary"
    expected = (str(tenant_id), str(channel), str(user_id), update_id, str(chat_id),
                _execution_owner(), bot_scope)
    if _VERIFIED_INGRESS.get() != expected:
        return None
    return _telegram_update_key(str(tenant_id), bot_scope, str(user_id), update_id)


def verified_telegram_idempotency_key(payload: Mapping[str, Any]) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    scope = _VERIFIED_INGRESS.get()
    if not isinstance(scope, tuple) or len(scope) != 7:
        return None
    tenant_id, channel, user_id, update_id, _chat_id, owner, bot_scope = scope
    if (owner != _execution_owner() or channel != "telegram" or
            type(update_id) is not int or update_id < 0):
        return None
    if (str(payload.get("tenant_id") or "") != tenant_id or
            str(payload.get("user_id") or "") != user_id):
        return None
    expected = _telegram_update_key(tenant_id, bot_scope, user_id, update_id)
    return expected if payload.get("idempotency_key") == expected else None


def telegram_action_fingerprint(action: str, payload: Mapping[str, Any]) -> str:
    stable_payload = dict(payload)
    for key in ("idempotency_key", "world_model_meta", "world_model_explainability",
                "constraint_explainability"):
        stable_payload.pop(key, None)
    meta = stable_payload.get("meta")
    if isinstance(meta, Mapping):
        stable_payload["meta"] = {
            key: value for key, value in meta.items()
            if key not in {"inbound_user_reply", "world_model_meta",
                           "world_model_explainability", "constraint_explainability"}
        }
    material = json.dumps(
        [str(action), stable_payload], sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode()
    return hashlib.sha256(material).hexdigest()


def _verified_signature(proof: Mapping[str, Any]) -> bool:
    key = SafetyKeyRegistry().get(str(proof.get("key_id") or ""))
    issued_at = proof.get("issued_at")
    return bool(key and key.active and not key.insecure_fallback and type(issued_at) is int
                and 0 <= int(time.time()) - issued_at <= 600
                and isinstance(proof.get("signature"), str)
                and hmac.compare_digest(proof["signature"], _proof_mac(proof, key.secret)))


def _single_target_non_campaign(action: str, payload: Mapping[str, Any]) -> bool:
    bulk_keys = ("recipients", "recipient_ids", "target_users", "audience", "segment_id",
                 "broadcast", "bulk", "batch_id", "campaign_id", "scheduled_at",
                 "marketing", "autonomous", "proactive", "charge_amount", "channel_policy")
    if (action != "send_message@v1" or str(payload.get("kind") or "").lower() in
            {"marketing", "campaign", "broadcast", "bulk", "proactive"} or
            any(payload.get(key) for key in bulk_keys)):
        return False
    track = payload.get("track_payload")
    blocked = ("campaign_id", "audience_id", "segment_id", "recipient_ids", "recipients", "target_users", "broadcast", "bulk", "scheduled_at")
    return not (isinstance(track, Mapping) and (any(track.get(key) for key in blocked) or
        ("marketing_variant" in track and not (payload.get("track_event_type") == "tariffs_viewed"
            and set(track) == {"marketing_variant"} and isinstance(track["marketing_variant"], str)
            and 0 < len(track["marketing_variant"]) <= 32))))

def _zero_cost(payload: Mapping[str, Any]) -> bool:
    try:
        raw = payload.get("estimated_cost", 0)
        return type(raw) is not bool and float(raw or 0) == 0.0
    except (TypeError, ValueError, OverflowError):
        return False


def is_budget_free_text_message(action: str, payload: Mapping[str, Any]) -> bool:
    """Classify zero-cost text for accounting, never for authorization."""
    if not isinstance(payload, Mapping) or not _single_target_non_campaign(action, payload):
        return False
    if not isinstance(payload.get("text"), str) or any(
            not isinstance(payload.get(k), str) or not payload[k].strip() for k in ("user_id", "tenant_id")):
        return False
    count = payload.get("recipient_count")
    if count is not None and (type(count) is not int or count != 1):
        return False
    if any(payload.get(key) for key in ("economy", "requested_budget", "budget_delta", "amount", "payment_id")):
        return False
    allowed = {"tenant_id", "user_id", "text", "channel", "chat_id", "reply_markup",
               "callback_query_id", "track_event_type", "track_payload", "product_id",
               "domain", "product_version", "actor_id", "idempotency_key", "world_model_meta",
               "meta", "recipient_count", "business_id", "goal_id", "autonomy_tier", "estimated_cost"}
    if set(payload) - allowed:
        return False
    meta = payload.get("meta")
    if meta is not None and not isinstance(meta, Mapping):
        return False
    unsafe = ("requested_budget", "budget_delta", "estimated_cost", "amount", "charge_amount",
              "campaign_id", "autonomous", "broadcast")
    if isinstance(meta, Mapping) and (any(meta.get(k) for k in unsafe) or
                                      ("inbound_user_reply" in meta and not is_routine_reply(action, payload))):
        return False
    return _zero_cost(payload)

def is_routine_reply(action: str, payload: Mapping[str, Any]) -> bool:
    """Only zero-cost, single-recipient, inbound-bound sends bypass autonomous budgets."""
    if not _single_target_non_campaign(action, payload):
        return False
    meta = payload.get("meta")
    proof = meta.get("inbound_user_reply") if isinstance(meta, Mapping) else None
    if not isinstance(proof, Mapping) or proof.get("channel") not in ALL_CHANNELS or not _verified_signature(proof):
        return False
    channel, event_id = proof["channel"], proof.get("update_id")
    tenant_matches = bool(proof.get("tenant_id")) and str(proof["tenant_id"]) == str(payload.get("tenant_id") or "")
    valid = (type(event_id) is int and event_id >= 0) if channel == "telegram" else (
        isinstance(event_id, str) and bool(event_id.strip()) and len(event_id) <= 256)
    recipient, count = payload.get("user_id"), payload.get("recipient_count")
    if (not tenant_matches or not valid or
            proof.get("content_sha256") != hashlib.sha256(str(payload.get("text") or "").encode()).hexdigest()
            or not isinstance(recipient, str) or not recipient.strip() or proof.get("user_id") != recipient
            or str(payload.get("channel") or "").strip().lower() != channel
            or str(payload.get("chat_id") or recipient) != str(proof.get("chat_id") or recipient)
            or (count is not None and (type(count) is not int or count != 1))):
        return False
    return _zero_cost(payload)

# Read projection accounting never substitutes for authorization or other controls.
_READ_COCKPIT = frozenset({"menu", "work", "today", "bookings", "growth", "growth-now", "partners", "ladder", "manage", "messengers", "connections", "switch", "growth-an", "money", "services", "calendar", "customers", "customer", "cust-time", "events", "automation", "settings",
    "team", "member", "sales", "sales-recent", "sales-actions", "sales-handoffs", "sales-lead", "prices", "payments", "pay-refund", "growth-report", "bk-open", "bk-months", "bk-dates", "bk-times", "bk-dur", "ev-conduct", "ev-texts"})
_READ_FIELDS = frozenset({"tenant_id", "business_id", "user_id", "actor_id", "op", "arg", "callback_query_id",
    "product_id", "domain", "product_version", "goal_id", "autonomy_tier", "idempotency_key", "world_model_meta", "meta", "estimated_cost"})

def is_budget_free_read_projection(action: str, payload: Mapping[str, Any]) -> bool:
    return _free_management(action, payload, local_write=False)

def is_budget_free_local_management(action: str, payload: Mapping[str, Any]) -> bool:
    return _free_management(action, payload, local_write=True)

def _free_management(action: str, payload: Mapping[str, Any], *, local_write: bool) -> bool:
    """Exempt only exact, zero-cost read projections, not authorization."""
    if not isinstance(payload, Mapping) or set(payload) - _READ_FIELDS:
        return False
    op, arg = payload.get("op"), str(payload.get("arg") or "")
    parts = arg[4:].split(":") if isinstance(payload.get("arg", ""), str) and arg.startswith("cpm:") and len(arg) <= 64 else []
    read_screen = (not arg or (bool(parts) and len(parts) <= 3 and parts[0] in _READ_COCKPIT
        and all(p and len(p) <= 40 and all(c.isascii() and (c.isalnum() or c in "_-") for c in p) for p in parts[1:])
        and (parts[0] not in {"team", "payments", "partners", "bookings", "customers"}
             or all(p.isdecimal() and len(p) <= 7 for p in parts[1:]))))
    allowed = ((action == "business_ops_summary@v1" and op == "cockpit" and read_screen) or
               (action == "business_ops_summary@v1" and op == "admin_analytics" and arg in ADMIN_ANALYTICS_ROUTES) or
               (action == "partners@v1" and op == "rank" and isinstance(payload.get("arg", ""), str) and len(arg) <= 200) or
               ((action, op) in {("sales_pipeline@v1", "list"), ("bookings@v1", "ad_channels"),
                                 ("business_admin@v1", "notifications_show")} and not arg))
    if local_write:
        allowed = (action == "business_admin@v1" and op in {"notifications_toggle", "notifications_level"}
                   and payload.get("arg", "") == "" and payload.get("actor_id") == payload.get("user_id"))
    if not allowed or any(not isinstance(payload.get(k), str) or not payload[k].strip() for k in ("tenant_id", "user_id")):
        return False
    meta = payload.get("meta")
    if meta is not None and (not isinstance(meta, Mapping) or any(meta.get(k) for k in (
        "amount", "estimated_cost", "charge_amount", "requested_budget", "budget_delta", "autonomous", "campaign_id", "broadcast"))):
        return False
    return _zero_cost(payload)
