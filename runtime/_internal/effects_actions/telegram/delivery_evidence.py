from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANON_TELEGRAM_DELIVERY_EVIDENCE = True


def _external_refs(meta: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    receipt = meta.get("receipt") if isinstance(meta.get("receipt"), Mapping) else {}
    receipt_metadata = (
        receipt.get("metadata")
        if isinstance(receipt.get("metadata"), Mapping)
        else {}
    )
    for value in (
        meta.get("external_id"),
        receipt.get("external_id"),
        receipt_metadata.get("external_id"),
        meta.get("delivery_key"),
    ):
        text = str(value or "").strip()
        if text and text not in refs:
            refs.append(text)
    return refs


def build_delivery_evidence(*, ok: bool, meta: Mapping[str, Any] | None, action_type: str) -> dict[str, Any]:
    payload = dict(meta or {})
    finalized = bool(payload.get("delivery_finalized", False))
    phase = str(payload.get("delivery_phase") or "").strip().casefold()
    mode = str(payload.get("mode") or "").strip().casefold()
    accepted_for_delivery = bool(ok) and (
        phase == "accepted_for_delivery"
        or mode in {"queued", "accepted"}
        or (bool(payload.get("dedup")) and not finalized)
    )
    verified = bool(finalized or accepted_for_delivery)

    if finalized:
        source = "connector"
        status = "verified"
        confidence = 1.0
    elif accepted_for_delivery:
        source = "ledger"
        status = "observed"
        confidence = 1.0
    else:
        source = "connector"
        status = "failed" if not ok else "observed"
        confidence = 0.0 if not ok else 1.0

    return {
        "source": source,
        "action_type": str(action_type),
        "verified": verified,
        "status": status,
        "summary": phase or mode or status,
        "external_refs": _external_refs(payload),
        "confidence": confidence,
        "payload": {
            "delivery_phase": phase or None,
            "delivery_finalized": finalized,
            "mode": mode or None,
            "dedup": bool(payload.get("dedup", False)),
        },
    }


__all__ = ["CANON_TELEGRAM_DELIVERY_EVIDENCE", "build_delivery_evidence"]
