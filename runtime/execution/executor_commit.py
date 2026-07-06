"""Commit/outbox helpers for RuntimeExecutor.

These helpers provide one canonical adapter layer between the executor and
existing runtime outbox implementations and reliability.outbox_store-compatible
implementations.

No business logic lives here.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any

from reliability.outbox_store import OutboxMessage, OutboxState, canonical_payload_digest


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _decision_payload(decision: Any) -> dict[str, Any]:
    return _safe_dict(getattr(decision, "payload", {}) or {})


def _decision_tenant_id(decision: Any) -> str:
    payload = _decision_payload(decision)
    tenant_id = str(payload.get("tenant_id") or payload.get("tenant") or "default").strip()
    return tenant_id or "default"


def _decision_topic(decision: Any) -> str:
    action = str(getattr(decision, "action", "") or "").strip()
    return f"runtime.effect.{action}" if action else "runtime.effect.unknown"


def _decision_effect_key(decision: Any) -> str:
    payload = _decision_payload(decision)
    explicit = str(payload.get("effect_key") or payload.get("action_id") or "").strip()
    if explicit:
        return explicit
    return str(getattr(decision, "decision_id", "") or "").strip()


def _decision_message_payload(decision: Any) -> dict[str, Any]:
    payload = _decision_payload(decision)
    return {
        "tenant_id": _decision_tenant_id(decision),
        "decision_id": str(getattr(decision, "decision_id", "") or ""),
        "correlation_id": str(getattr(decision, "correlation_id", "") or ""),
        "action": str(getattr(decision, "action", "") or ""),
        "effect_key": _decision_effect_key(decision),
        "payload": payload,
        "payload_digest": canonical_payload_digest(payload),
    }


def build_delivery_metadata(*, decision: Any, mode: str, owner_id: str) -> dict[str, Any]:
    payload = _decision_payload(decision)
    message_payload = _decision_message_payload(decision)
    return {
        "mode": str(mode),
        "owner_id": str(owner_id),
        "action": str(getattr(decision, "action", "") or ""),
        "correlation_id": str(getattr(decision, "correlation_id", "") or ""),
        "decision_id": str(getattr(decision, "decision_id", "") or ""),
        "effect_key": _decision_effect_key(decision),
        "effect_kind": "runtime_effect",
        "tenant_id": _decision_tenant_id(decision),
        "payload_digest": canonical_payload_digest(message_payload),
        "action_payload_digest": canonical_payload_digest(payload),
    }


def enqueue_once(outbox: Any, *, decision: Any) -> None:
    if outbox is None:
        return
    decision_id = str(getattr(decision, "decision_id", "") or "")
    correlation_id = str(getattr(decision, "correlation_id", "") or "")
    action = str(getattr(decision, "action", "") or "")
    payload = _decision_payload(decision)
    if hasattr(outbox, "enqueue_once"):
        canonical_json_bytes = importlib.import_module("core.utils.canonical").canonical_json_bytes
        payload_json = canonical_json_bytes(payload).decode("utf-8")
        outbox.enqueue_once(
            decision_id=decision_id,
            correlation_id=correlation_id,
            action=action,
            payload_json=payload_json,
        )
        return
    if hasattr(outbox, "enqueue"):
        message_payload = _decision_message_payload(decision)
        effect_key = _decision_effect_key(decision)
        message = OutboxMessage(
            tenant_id=_decision_tenant_id(decision),
            message_id=decision_id,
            topic=_decision_topic(decision),
            dedupe_key=effect_key or decision_id,
            payload=message_payload,
            trace_id=correlation_id or None,
            decision_id=decision_id or None,
            effect_key=effect_key or None,
            effect_kind="runtime_effect",
            payload_digest=canonical_payload_digest(message_payload),
        )
        outbox.enqueue(message)
        return
    raise AttributeError("outbox has neither enqueue_once nor enqueue")


def claim_or_skip(outbox: Any, *, decision_id: str, tenant_id: str = "default", owner_id: str = "runtime-executor", claim_ttl_seconds: int = 60) -> bool:
    if outbox is None:
        return True
    if hasattr(outbox, "claim"):
        try:
            claimed = outbox.claim(str(decision_id))
            return bool(claimed)
        except TypeError:
            claimed = outbox.claim(
                tenant_id=str(tenant_id),
                message_id=str(decision_id),
                owner_id=str(owner_id),
                claim_ttl_seconds=int(claim_ttl_seconds),
            )
            return claimed is not None
    return True


def mark_delivered(
    outbox: Any,
    *,
    decision_id: str,
    tenant_id: str = "default",
    owner_id: str = "runtime-executor",
    backend_name: str = "runtime_executor",
    external_id: str | None = None,
    payload_digest: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    if outbox is None:
        return
    if hasattr(outbox, "mark_delivered"):
        try:
            outbox.mark_delivered(str(decision_id))
            return
        except TypeError:
            outbox.mark_delivered(
                tenant_id=str(tenant_id),
                message_id=str(decision_id),
                owner_id=str(owner_id),
                backend_name=str(backend_name),
                external_id=None if external_id is None else str(external_id),
                payload_digest=None if payload_digest is None else str(payload_digest),
                metadata=dict(metadata or {}),
            )
            return
    raise AttributeError("outbox has no mark_delivered")


def move_to_dead_letter(
    outbox: Any,
    *,
    decision_id: str,
    tenant_id: str = "default",
    owner_id: str = "runtime-executor",
    error: str = "",
) -> None:
    if outbox is None or not hasattr(outbox, "move_to_dead_letter"):
        return
    try:
        outbox.move_to_dead_letter(str(decision_id))
    except TypeError:
        outbox.move_to_dead_letter(
            tenant_id=str(tenant_id),
            message_id=str(decision_id),
            owner_id=str(owner_id),
            error=str(error),
        )


def status(outbox: Any, *, decision_id: str, tenant_id: str = "default") -> str | None:
    if outbox is None:
        return None
    if hasattr(outbox, "status"):
        return outbox.status(str(decision_id))
    if hasattr(outbox, "get"):
        try:
            row = outbox.get(str(decision_id))
        except TypeError:
            row = outbox.get(tenant_id=str(tenant_id), message_id=str(decision_id))
        if row is None:
            return None
        if isinstance(row, Mapping):
            return str(row.get("status") or row.get("state") or "").strip() or None
        state = getattr(row, "state", None)
        if isinstance(state, OutboxState):
            return state.value
        if state is not None:
            return str(state)
    return None


def has_pending(outbox: Any, *, decision_id: str, tenant_id: str = "default") -> bool:
    current = status(outbox, decision_id=decision_id, tenant_id=tenant_id)
    return current in {"pending", "delivering", "inflight"}


def get_delivery_info(outbox: Any, *, decision_id: str, tenant_id: str = "default") -> dict[str, Any] | None:
    if outbox is None or not hasattr(outbox, "get"):
        return None
    try:
        row = outbox.get(str(decision_id))
    except TypeError:
        row = outbox.get(tenant_id=str(tenant_id), message_id=str(decision_id))
    if row is None:
        return None
    if isinstance(row, Mapping):
        info = dict(row)
        if isinstance(info.get("delivery_metadata"), Mapping):
            info["delivery_metadata"] = dict(info.get("delivery_metadata") or {})
        return info
    info: dict[str, Any] = {
        "message_id": getattr(row, "message_id", decision_id),
        "tenant_id": getattr(row, "tenant_id", tenant_id),
        "backend_name": getattr(row, "backend_name", None),
        "external_id": getattr(row, "external_id", None),
        "delivery_attempts": getattr(row, "delivery_attempts", None),
        "effect_key": getattr(row, "effect_key", None),
        "effect_kind": getattr(row, "effect_kind", None),
        "payload_digest": getattr(row, "payload_digest", None) or getattr(row, "resolved_payload_digest", None),
        "state": getattr(getattr(row, "state", None), "value", getattr(row, "state", None)),
        "delivered_at": None if getattr(row, "delivered_at", None) is None else row.delivered_at.isoformat(),
        "delivery_metadata": dict(getattr(row, "delivery_metadata", {}) or {}),
    }
    return info
