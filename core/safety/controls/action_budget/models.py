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
                                 update_id: object, chat_id: str = "") -> Iterator[None]:
    token = _VERIFIED_INGRESS.set((str(tenant_id), str(channel), str(user_id), update_id,
                                   str(chat_id), _execution_owner()))
    try:
        yield
    finally:
        _VERIFIED_INGRESS.reset(token)


def _proof_mac(proof: Mapping[str, Any], secret: bytes) -> str:
    material = json.dumps([proof.get(field) for field in _PROOF_FIELDS],
                          separators=(",", ":"), ensure_ascii=False).encode()
    return hmac.new(secret, b"businesaios:inbound-reply:v1:" + material, hashlib.sha256).hexdigest()


def issue_verified_reply(*, tenant_id: str, channel: str, user_id: str,
                         update_id: object, chat_id: str = "", text: str = "") -> dict[str, Any] | None:
    if _VERIFIED_INGRESS.get() != (tenant_id, channel, user_id, update_id, chat_id, _execution_owner()):
        return None
    key = SafetyKeyRegistry().current
    if key.insecure_fallback or not key.active:
        return None
    proof = dict(tenant_id=tenant_id, channel=channel, user_id=user_id, update_id=update_id,
                 chat_id=chat_id, content_sha256=hashlib.sha256(text.encode()).hexdigest(),
                 issued_at=int(time.time()), key_id=key.key_id)
    proof["signature"] = _proof_mac(proof, key.secret)
    return proof


def _verified_signature(proof: Mapping[str, Any]) -> bool:
    key = SafetyKeyRegistry().get(str(proof.get("key_id") or ""))
    issued_at = proof.get("issued_at")
    return bool(key and key.active and not key.insecure_fallback and type(issued_at) is int
                and 0 <= int(time.time()) - issued_at <= 600
                and isinstance(proof.get("signature"), str)
                and hmac.compare_digest(proof["signature"], _proof_mac(proof, key.secret)))


def is_budget_free_text_message(action: str, payload: Mapping[str, Any]) -> bool:
    """Pure single-recipient text delivery requires no spending or action quota.

    This is accounting classification, not authorization: tenant isolation,
    permission checks, rate limits, transport identity and signature enforcement
    still run on the regular canonical execution path. Paid operations and
    bulk/campaign sends are not classified as ordinary text delivery.
    """
    if action != "send_message@v1" or not isinstance(payload, Mapping):
        return False
    if not isinstance(payload.get("text"), str):
        return False
    if not isinstance(payload.get("user_id"), str) or not payload["user_id"].strip():
        return False
    tenant = payload.get("tenant_id")
    if not isinstance(tenant, str) or not tenant.strip():
        return False
    count = payload.get("recipient_count")
    if count is not None and (type(count) is not int or count != 1):
        return False
    if str(payload.get("kind") or "").lower() in {
        "marketing", "campaign", "broadcast", "bulk", "proactive",
    }:
        return False
    if any(payload.get(field) for field in (
        "recipients", "recipient_ids", "target_users", "audience", "segment_id",
        "broadcast", "bulk", "batch_id", "campaign_id", "scheduled_at",
        "marketing", "autonomous", "proactive", "charge_amount", "channel_policy",
        "economy", "requested_budget", "budget_delta", "amount", "payment_id",
    )):
        return False
    # Strictly reject extra fields that can hide paid / bulk work while
    # allowing the already sealed provider routing and inbound proof metadata.
    allowed_fields = {
        "tenant_id", "user_id", "text", "channel", "chat_id",
        "reply_markup", "callback_query_id", "track_event_type", "track_payload",
        "product_id", "domain", "product_version", "actor_id",
        "idempotency_key", "world_model_meta", "meta", "recipient_count",
        "business_id", "goal_id", "autonomy_tier", "estimated_cost",
    }
    if set(payload) - allowed_fields:
        return False
    meta = payload.get("meta")
    if meta is not None and not isinstance(meta, Mapping):
        return False
    if isinstance(meta, Mapping) and any(meta.get(field) for field in (
        "requested_budget", "budget_delta", "estimated_cost", "amount",
        "charge_amount", "campaign_id", "autonomous", "broadcast",
    )):
        return False
    tracking = payload.get("track_payload")
    if isinstance(tracking, Mapping) and any(tracking.get(field) for field in (
        "campaign_id", "audience_id", "segment_id", "marketing_variant",
        "recipient_ids", "recipients", "target_users", "broadcast", "bulk",
        "scheduled_at",
    )):
        return False
    cost = payload.get("estimated_cost", 0)
    if isinstance(cost, bool):
        return False
    try:
        cost_value = float(cost or 0)
    except (TypeError, ValueError, OverflowError):
        return False
    return cost_value == 0 and cost_value == cost_value


def is_routine_reply(action: str, payload: Mapping[str, Any]) -> bool:
    """Only zero-cost, single-recipient, inbound-bound sends bypass autonomous budgets."""
    if action != "send_message@v1" or str(payload.get("kind") or "").lower() in {
        "marketing", "campaign", "broadcast", "bulk", "proactive",
    } or any(payload.get(field) for field in (
        "recipients", "recipient_ids", "target_users", "audience", "segment_id",
        "broadcast", "bulk", "batch_id", "campaign_id", "scheduled_at",
        "marketing", "autonomous", "proactive", "charge_amount", "channel_policy",
    )):
        return False
    track = payload.get("track_payload")
    if isinstance(track, Mapping) and any(track.get(field) for field in (
        "campaign_id", "audience_id", "segment_id", "marketing_variant", "recipient_ids",
        "recipients", "target_users", "broadcast", "bulk", "scheduled_at",
    )):
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
    text_digest = hashlib.sha256(str(payload.get("text") or "").encode()).hexdigest()
    if (not tenant_matches or not valid or proof.get("content_sha256") != text_digest
            or not isinstance(recipient, str) or not recipient.strip()
            or proof.get("user_id") != recipient
            or str(payload.get("channel") or "").strip().lower() != channel
            or str(payload.get("chat_id") or recipient) != str(proof.get("chat_id") or recipient)
            or (count is not None and (type(count) is not int or count != 1))):
        return False
    try:
        return float(payload.get("estimated_cost") or 0.0) == 0.0
    except (ValueError, TypeError, OverflowError):
        return False
