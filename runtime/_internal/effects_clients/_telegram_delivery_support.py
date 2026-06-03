from __future__ import annotations

import hashlib
import json
import time
from typing import Any
from collections.abc import Mapping

from runtime.platform.delivery_state import ACCEPTED_PHASE, FINALIZED_PHASE, RECOVERY_PHASE


def stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def delivery_key(*, method: str, chat_id: str, payload: Mapping[str, Any]) -> str:
    seed = {
        "method": str(method),
        "chat_id": str(chat_id),
        "payload_digest": payload_digest(payload),
    }
    return hashlib.sha256(stable_json(seed).encode("utf-8")).hexdigest()


def phase_from_receipt(receipt: Mapping[str, Any] | None, *, default: str = FINALIZED_PHASE) -> str:
    if not isinstance(receipt, Mapping):
        return str(default)
    metadata = receipt.get("metadata")
    phase = receipt.get("delivery_phase")
    if not phase and isinstance(metadata, Mapping):
        phase = metadata.get("delivery_phase")
    return str(phase or default)


def build_delivery_metadata(
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
    metadata = {
        "method": str(method),
        "chat_id": None if chat_id is None else str(chat_id),
        "payload": dict(payload),
        "timeout_s": int(timeout_s or 0),
        "priority": priority,
        "critical": bool(critical),
        "mode": str(mode),
        "delivery_key": str(delivery_key),
        "payload_digest": str(payload_digest),
    }
    metadata.update(dict(extra or {}))
    return metadata


def accepted_receipt_is_stale(receipt: Mapping[str, Any] | None) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    phase = phase_from_receipt(receipt, default=ACCEPTED_PHASE)
    if phase not in {ACCEPTED_PHASE, RECOVERY_PHASE}:
        return False
    metadata = receipt.get("metadata") if isinstance(receipt.get("metadata"), Mapping) else {}
    timeout_s = int(metadata.get("timeout_s") or 0)
    stale_after_ms = max(30000, timeout_s * 2000)
    accepted_at_ms = receipt.get("accepted_at_ms") or receipt.get("delivered_at_ms") or 0
    try:
        accepted_ms = int(accepted_at_ms or 0)
    except Exception:
        accepted_ms = 0
    if accepted_ms <= 0:
        return False
    return int(time.time() * 1000) - accepted_ms >= stale_after_ms
