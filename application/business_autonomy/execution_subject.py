from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from application.business_autonomy.contracts import BusinessExecutionRequest
from governance.persistence_codec import to_jsonable

CANON_BUSINESS_AUTONOMY_EXECUTION_SUBJECT = True
_IDEMPOTENCY_SCOPE_MARKER = "|subject-sha256="


def business_execution_subject(request: BusinessExecutionRequest) -> dict[str, Any]:
    """Return the immutable identity of a DecisionCore-selected execution.

    The subject contains no policy or decision logic. It only binds governance,
    idempotency and evidence to exactly the request that the canonical decision
    path selected.
    """

    constraints = [
        {
            "name": str(item.name),
            "value": to_jsonable(item.value),
            "severity": str(item.severity.value),
            "reason": None if item.reason is None else str(item.reason),
        }
        for item in request.envelope.constraints
    ]
    constraints.sort(
        key=lambda item: (
            item["name"],
            item["severity"],
            json.dumps(item["value"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            str(item["reason"] or ""),
        )
    )
    metadata = dict(request.envelope.metadata or {})
    subject = {
        "tenant_id": str(metadata.get("tenant_id") or "").strip(),
        "business_id": str(request.envelope.business_id or "").strip(),
        "goal_id": str(request.envelope.goal_id or "").strip(),
        "goal_type": str(request.envelope.goal_type or "").strip(),
        "goal_payload": to_jsonable(dict(request.envelope.goal_payload or {})),
        "priority": int(request.envelope.priority),
        "simulation": bool(request.envelope.simulation),
        "constraints": constraints,
        "integration_mode": str(request.integration_mode.value),
        "idempotency_key": str(request.idempotency_key or request.correlation_id or "").strip(),
    }
    return to_jsonable(subject)


def business_execution_fingerprint(request: BusinessExecutionRequest) -> str:
    serialized = json.dumps(
        business_execution_subject(request),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def stable_business_idempotency_key(request: BusinessExecutionRequest) -> str:
    tenant_id = str(request.envelope.metadata.get("tenant_id") or "").strip()
    business_id = str(request.envelope.business_id or "").strip()
    raw_key = str(request.idempotency_key or request.correlation_id or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required for idempotency")
    if not business_id:
        raise ValueError("business_id is required for idempotency")
    if not raw_key:
        raise ValueError("idempotency_key is required")
    return f"{tenant_id}:{business_id}:{raw_key}"


def scoped_business_idempotency_token(request: BusinessExecutionRequest) -> str:
    return (
        stable_business_idempotency_key(request)
        + _IDEMPOTENCY_SCOPE_MARKER
        + business_execution_fingerprint(request)
    )


def parse_business_idempotency_token(token: str) -> tuple[str, str]:
    text = str(token or "").strip()
    if _IDEMPOTENCY_SCOPE_MARKER not in text:
        raise ValueError("canonical idempotency token is missing execution fingerprint")
    stable_key, fingerprint = text.rsplit(_IDEMPOTENCY_SCOPE_MARKER, 1)
    stable_key = stable_key.strip()
    fingerprint = fingerprint.strip().lower()
    if not stable_key:
        raise ValueError("canonical idempotency stable key is required")
    if len(fingerprint) != 64 or any(character not in "0123456789abcdef" for character in fingerprint):
        raise ValueError("canonical idempotency fingerprint must be sha256 hex")
    return stable_key, fingerprint


def business_execution_approval_id(request: BusinessExecutionRequest) -> str:
    subject = business_execution_subject(request)
    fingerprint = business_execution_fingerprint(request)
    return (
        "business-autonomy:"
        f"{subject['tenant_id']}:"
        f"{subject['business_id']}:"
        f"{subject['goal_id']}:"
        f"{fingerprint[:24]}"
    )


def approval_subject_metadata(request: BusinessExecutionRequest) -> Mapping[str, object]:
    return {
        "business_id": request.envelope.business_id,
        "goal_id": request.envelope.goal_id,
        "goal_type": request.envelope.goal_type,
        "subject_fingerprint": business_execution_fingerprint(request),
        "execution_subject": business_execution_subject(request),
    }


__all__ = [
    "CANON_BUSINESS_AUTONOMY_EXECUTION_SUBJECT",
    "approval_subject_metadata",
    "business_execution_approval_id",
    "business_execution_fingerprint",
    "business_execution_subject",
    "parse_business_idempotency_token",
    "scoped_business_idempotency_token",
    "stable_business_idempotency_key",
]
