from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from execution.evidence.result import EvidenceResult


CANON_EVIDENCE_BASE = True


def _dictish(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _tuple_refs(*parts: Any) -> tuple[str, ...]:
    refs: list[str] = []
    for part in parts:
        if isinstance(part, str) and part.strip():
            refs.append(part.strip())
        elif isinstance(part, (list, tuple, set)):
            refs.extend(str(item).strip() for item in part if str(item).strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            ordered.append(ref)
    return tuple(ordered)


@dataclass(frozen=True)
class EvidenceVerifier(ABC):
    action_prefixes: tuple[str, ...] = ()

    @abstractmethod
    def verify(self, request: Any, action: Any, action_result: Any, connector_result: Any) -> EvidenceResult:
        raise NotImplementedError

    def _verify_from_payload(self, *, status: str, request: Any, action: Any, action_result: Any, connector_result: Any) -> EvidenceResult:
        del request
        action_payload = _dictish(getattr(action_result, "payload", {}))
        effector = _dictish(action_payload.get("effector"))
        effector_evidence = _dictish(effector.get("evidence"))
        connector_payload = _dictish(connector_result)
        connector_verify = _dictish(connector_payload.get("verify"))
        independent_effector_verify = bool(effector_evidence.get("independently_verified"))
        effector_verified = bool(effector.get("verified"))
        payload_verified = bool(action_payload.get("verified"))
        connector_verified = bool(connector_verify.get("ok"))
        verified = bool(connector_verified or independent_effector_verify or effector_verified or payload_verified)
        external_refs = _tuple_refs(
            action_payload.get("external_ref"),
            action_payload.get("external_refs"),
            effector.get("external_ref"),
            effector_evidence.get("external_ref"),
            effector_evidence.get("external_refs"),
            connector_verify.get("external_ref"),
            connector_verify.get("external_refs"),
        )
        confidence = 1.0 if connector_verified or effector_verified or payload_verified else (0.9 if independent_effector_verify else (0.25 if bool(getattr(action_result, "executed", False)) else 0.0))
        code = str(connector_verify.get("code") or effector_evidence.get("verification_code") or effector.get("code") or action_payload.get("verification_code") or ("verified" if verified else "verification_missing"))
        message = str(connector_verify.get("message") or effector_evidence.get("verification_message") or effector.get("message") or action_payload.get("verification_message") or ("evidence verified" if verified else "evidence missing or unverified"))
        source = (
            "connector_verify"
            if connector_verify
            else (
                "effector_verified"
                if effector_verified
                else ("payload_verified" if payload_verified else ("independent_effector_evidence" if independent_effector_verify else "none"))
            )
        )
        payload = {
            "action_type": str(getattr(action, "action_type", "")),
            "verification_source": source,
            "effector_status": effector.get("status"),
            "connector_result": connector_payload,
        }
        if effector_evidence:
            payload["effector_evidence"] = effector_evidence
        return EvidenceResult(
            verified=verified,
            status=status if verified else "unverified",
            confidence=confidence,
            external_refs=external_refs,
            code=code,
            message=message,
            payload=payload,
        )


__all__ = ["CANON_EVIDENCE_BASE", "EvidenceVerifier"]
