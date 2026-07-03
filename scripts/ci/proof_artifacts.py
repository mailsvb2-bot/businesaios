from __future__ import annotations

from collections.abc import Mapping, Sequence

CANON_PRODUCTION_PROOF_ARTIFACT_GUARD = True

_PRODUCTION_READY_CLAIM_FIELDS = ("claims_production_ready", "production_ready")


def _present(value: object) -> bool:
    return bool(str(value or "").strip())


def production_ready_claim_violations(*, payload: Mapping[str, object], artifact_name: str) -> list[str]:
    violations: list[str] = []
    for field in _PRODUCTION_READY_CLAIM_FIELDS:
        if payload.get(field) is True:
            violations.append(f"{artifact_name}_{field}_forbidden")
    return violations


def required_text_field_violations(
    *,
    payload: Mapping[str, object],
    artifact_name: str,
    fields: Sequence[str],
) -> list[str]:
    violations: list[str] = []
    for field in fields:
        if not _present(payload.get(field)):
            violations.append(f"{artifact_name}_{field}_required")
    return violations


def evidence_kind_violations(
    *,
    payload: Mapping[str, object],
    artifact_name: str,
    allowed_kinds: Sequence[str],
) -> list[str]:
    if not allowed_kinds:
        return []
    kind = str(payload.get("evidence_kind") or "").strip()
    if kind in set(allowed_kinds):
        return []
    return [f"{artifact_name}_evidence_kind_invalid"]


def proof_artifact_violations(
    *,
    payload: Mapping[str, object],
    artifact_name: str,
    required_text_fields: Sequence[str] = (),
    allowed_evidence_kinds: Sequence[str] = (),
) -> list[str]:
    """Return fail-closed violations for a proof artifact.

    Production-readiness artifacts are allowed to prove a narrow fact only. They
    must not self-claim production readiness; the release aggregator owns that
    final decision. Ready real-runtime evidence must also carry provenance, so a
    hand-written ``{"status": "ready"}`` cannot satisfy the release contract.
    """

    violations = production_ready_claim_violations(payload=payload, artifact_name=artifact_name)
    if payload.get("status") != "ready":
        return violations
    violations.extend(
        required_text_field_violations(
            payload=payload,
            artifact_name=artifact_name,
            fields=required_text_fields,
        )
    )
    violations.extend(
        evidence_kind_violations(
            payload=payload,
            artifact_name=artifact_name,
            allowed_kinds=allowed_evidence_kinds,
        )
    )
    return violations


__all__ = [
    "CANON_PRODUCTION_PROOF_ARTIFACT_GUARD",
    "evidence_kind_violations",
    "production_ready_claim_violations",
    "proof_artifact_violations",
    "required_text_field_violations",
]
