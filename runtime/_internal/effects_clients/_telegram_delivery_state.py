from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.platform.delivery_state import FINALIZED_PHASE, RECOVERY_PHASE

from ._telegram_delivery_support import accepted_receipt_is_stale, build_delivery_metadata, phase_from_receipt


def existing_receipt(state: Any, *, delivery_key: str) -> dict[str, Any] | None:
    if state is None or not hasattr(state, "get_receipt"):
        return None
    try:
        receipt = state.get_receipt(str(delivery_key))
    except Exception:
        return None
    return dict(receipt or {}) if isinstance(receipt, Mapping) else None


def receipt_phase(receipt: Mapping[str, Any] | None, *, default: str = FINALIZED_PHASE) -> str:
    return phase_from_receipt(receipt, default=default)


def delivery_metadata(
    *,
    method: str,
    chat_id: str | None,
    payload: Mapping[str, Any],
    timeout_s: int,
    priority: Any,
    critical: bool,
    mode: str,
    delivery_key: str,
    payload_digest: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_delivery_metadata(
        method=method,
        chat_id=chat_id,
        payload=payload,
        timeout_s=timeout_s,
        priority=priority,
        critical=critical,
        mode=mode,
        delivery_key=delivery_key,
        payload_digest=payload_digest,
        extra=extra,
    )


def mark_transport_accepted(state: Any, *, delivery_key: str, payload_digest: str, metadata: Mapping[str, Any]) -> None:
    if state is None or not hasattr(state, "mark_accepted"):
        return
    try:
        state.mark_accepted(
            str(delivery_key),
            payload_digest=str(payload_digest),
            metadata=dict(metadata or {}),
        )
    except Exception:
        return


def mark_transport_delivered(
    state: Any,
    *,
    delivery_key: str,
    external_id: str | None,
    payload_digest: str,
    metadata: Mapping[str, Any],
) -> None:
    if state is None or not hasattr(state, "mark_delivered"):
        return
    try:
        state.mark_delivered(
            str(delivery_key),
            external_id=None if external_id is None else str(external_id),
            payload_digest=str(payload_digest),
            metadata=dict(metadata or {}),
        )
    except Exception:
        return


def recover_stale_receipt(state: Any, *, delivery_key: str, payload_digest: str, metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    if state is None or not hasattr(state, "mark_recovery_queued"):
        return None
    try:
        receipt = state.mark_recovery_queued(
            str(delivery_key),
            payload_digest=str(payload_digest),
            metadata=dict(metadata or {}),
        )
    except Exception:
        return None
    return dict(receipt or {}) if isinstance(receipt, Mapping) else None


def recover_inflight_accepted_receipts(state: Any, *, stale_after_ms: int, limit: int = 100) -> list[dict[str, Any]]:
    if state is None or not hasattr(state, "list_stale_accepted_receipts"):
        return []
    try:
        receipts = state.list_stale_accepted_receipts(older_than_ms=int(stale_after_ms), limit=int(limit))
    except Exception:
        return []
    recovered: list[dict[str, Any]] = []
    for receipt in receipts or []:
        if not isinstance(receipt, Mapping):
            continue
        metadata = receipt.get("metadata") if isinstance(receipt.get("metadata"), Mapping) else {}
        updated = recover_stale_receipt(
            state,
            delivery_key=str(receipt.get("message_id") or ""),
            payload_digest=str(receipt.get("payload_digest") or metadata.get("payload_digest") or ""),
            metadata={
                **dict(metadata),
                "recovery_reason": "stale_accepted_receipt",
                "delivery_phase": RECOVERY_PHASE,
            },
        )
        if isinstance(updated, Mapping):
            recovered.append(dict(updated))
    return recovered


def accepted_receipt_stale(receipt: Mapping[str, Any] | None) -> bool:
    return accepted_receipt_is_stale(receipt)
