from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from execution.verification.evidence_types import evidence_status_is_positive
from execution.verification.verification_contract import verification_policy_from_action

CANON_RUNTIME_EVIDENCE_TRUST_POLICY = True

_TRUSTED_ROUTER_SOURCES = frozenset(
    {
        "effect_router",
        "evidence_router",
        "connector",
        "platform",
        "crm",
        "payment_gateway",
        "website",
        "callback",
        "ledger",
    }
)
_INTERNAL_EVIDENCE_SOURCES = frozenset(
    {
        "",
        "executor",
        "runtime_execution_contract",
        "feedback",
        "feedback_contract",
        "feedback_connector",
        "none",
        "unknown",
        "unattributed",
        "unattributed_router",
    }
)


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _source(value: object) -> str:
    return str(value or "").strip().casefold()


def _router_source_is_trusted(value: object) -> bool:
    return _source(value) in _TRUSTED_ROUTER_SOURCES


def _external_source_is_trusted(value: object) -> bool:
    source = _source(value)
    return bool(source) and source not in _INTERNAL_EVIDENCE_SOURCES


def extract_trusted_router_evidence(output: Mapping[str, Any]) -> dict[str, Any]:
    """Return only explicitly attributed router evidence.

    Legacy output keys remain readable for compatibility, but shape alone never
    upgrades a mapping into trusted external evidence. A canonical external
    source must be explicit.
    """

    for key in ("router_evidence", "verification", "evidence"):
        candidate = _safe_dict(output.get(key))
        if candidate and _router_source_is_trusted(candidate.get("source")):
            return candidate
    return {}


def _filter_connector_snapshots(value: object) -> list[dict[str, Any]]:
    rows: list[object]
    if isinstance(value, Mapping):
        rows = [value]
    elif isinstance(value, list | tuple):
        rows = list(value)
    else:
        return []

    trusted: list[dict[str, Any]] = []
    for row in rows:
        candidate = _safe_dict(row)
        if candidate and _external_source_is_trusted(candidate.get("source")):
            trusted.append(candidate)
    return trusted


def sanitize_feedback_payload(feedback: Mapping[str, Any] | None) -> dict[str, Any]:
    """Preserve feedback while preventing unattributed evidence promotion."""

    payload = _safe_dict(feedback)
    if not payload:
        return {}

    normalized = dict(payload)

    top_router = _safe_dict(normalized.get("router_result"))
    if top_router and not _router_source_is_trusted(top_router.get("source")):
        normalized.pop("router_result", None)

    if "connector_snapshots" in normalized:
        normalized["connector_snapshots"] = _filter_connector_snapshots(normalized.get("connector_snapshots"))

    evidence = _safe_dict(normalized.get("evidence"))
    if evidence:
        evidence = dict(evidence)
        nested_router = _safe_dict(evidence.get("router_result"))
        if nested_router and not _router_source_is_trusted(nested_router.get("source")):
            evidence.pop("router_result", None)

        if "connector_snapshots" in evidence:
            evidence["connector_snapshots"] = _filter_connector_snapshots(evidence.get("connector_snapshots"))

        has_structured_evidence = bool(evidence.get("router_result") or evidence.get("connector_snapshots"))
        if not has_structured_evidence and not _external_source_is_trusted(evidence.get("source")):
            normalized.pop("evidence", None)
        else:
            normalized["evidence"] = evidence

    return normalized


def external_confirmation_required(action: Mapping[str, Any]) -> bool:
    return bool(verification_policy_from_action(action).require_external_evidence)


def result_has_trusted_external_evidence(result: Mapping[str, Any]) -> bool:
    verification = _safe_dict(result.get("verification"))
    engine = _safe_dict(verification.get("engine"))
    evidence_rows = engine.get("evidence")
    if not isinstance(evidence_rows, list | tuple):
        return False

    for row in evidence_rows:
        item = _safe_dict(row)
        if not item or not evidence_status_is_positive(item.get("status")):
            continue
        kind = str(item.get("kind") or item.get("evidence_type") or "").strip().casefold()
        source = item.get("source")
        if kind == "router_result" and _router_source_is_trusted(source):
            return True
        if kind in {"connector_snapshot", "callback", "ledger_entry"} and _external_source_is_trusted(source):
            return True
    return False


__all__ = [
    "CANON_RUNTIME_EVIDENCE_TRUST_POLICY",
    "external_confirmation_required",
    "extract_trusted_router_evidence",
    "result_has_trusted_external_evidence",
    "sanitize_feedback_payload",
]
