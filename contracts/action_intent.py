from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any

CANON_ACTION_INTENT_CONTRACT = True


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _finite(value: object, name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True)
class ActionIntentV1:
    intent_id: str
    tenant_id: str
    business_id: str
    decision_id: str
    correlation_id: str
    action_type: str
    channel: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    payload_hash: str = ""
    objective_name: str = "profit_adjusted_growth"
    estimated_cost: float | None = None
    expected_value: float | None = None
    confidence: float | None = None
    reversible: bool | None = None
    requested_by: str = "sovereign_decision"
    agent_id: str = ""
    schema_version: int = 1
    evidence_refs: tuple[str, ...] = ()
    derived_fact_ref: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze(dict(self.payload or {})))
        requested_by = str(self.requested_by or "").strip()
        object.__setattr__(self, "requested_by", requested_by)
        object.__setattr__(self, "agent_id", str(self.agent_id or requested_by).strip())
        refs = tuple(dict.fromkeys(str(item).strip() for item in self.evidence_refs if str(item).strip()))
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "derived_fact_ref", str(self.derived_fact_ref or "").strip())

    def payload_copy(self) -> dict[str, Any]:
        return _thaw(self.payload)

    @property
    def goal_id(self) -> str | None:
        meta = self.payload.get("meta") if isinstance(self.payload, Mapping) else None
        meta_goal_id = str(meta.get("canonical_goal_id") or "").strip() if isinstance(meta, Mapping) else ""
        return meta_goal_id or None

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "decision_id": self.decision_id,
            "correlation_id": self.correlation_id,
            "action_type": self.action_type,
            "channel": self.channel,
            "payload": self.payload_copy(),
            "payload_hash": self.payload_hash,
            "objective_name": self.objective_name,
            "estimated_cost": self.estimated_cost,
            "expected_value": self.expected_value,
            "confidence": self.confidence,
            "reversible": self.reversible,
            "requested_by": self.requested_by,
            "agent_id": self.agent_id,
            "schema_version": self.schema_version,
            "evidence_refs": list(self.evidence_refs),
            "derived_fact_ref": self.derived_fact_ref,
        }

    def validate_contract(self) -> list[str]:
        identity = (
            "intent_id", "tenant_id", "business_id", "decision_id",
            "correlation_id", "action_type", "channel", "requested_by", "agent_id",
        )
        issues = [
            f"invalid:{name}" for name in identity
            if not str(getattr(self, name) or "").strip()
            or str(getattr(self, name)).strip() != str(getattr(self, name))
        ]
        if len(self.payload_hash) != 64 or any(ch not in "0123456789abcdef" for ch in self.payload_hash):
            issues.append("invalid:payload_hash")
        if self.objective_name != "profit_adjusted_growth":
            issues.append("invalid:objective_name")
        payload_goal_id = str(self.payload.get("goal_id") or "").strip()
        meta = self.payload.get("meta") if isinstance(self.payload, Mapping) else None
        meta_goal_id = str(meta.get("canonical_goal_id") or "").strip() if isinstance(meta, Mapping) else ""
        if payload_goal_id and meta_goal_id and payload_goal_id != meta_goal_id:
            issues.append("invalid:goal_id")
        if self.schema_version != 1:
            issues.append("invalid:schema_version")
        if self.estimated_cost is not None and self.estimated_cost < 0:
            issues.append("invalid:estimated_cost")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            issues.append("invalid:confidence")
        return issues

    @classmethod
    def from_projection(
        cls, *, intent_id: str, tenant_id: str, business_id: str, decision_id: str,
        correlation_id: str, action_type: str, channel: str, payload: Mapping[str, Any],
        payload_hash: str, requested_by: str = "sovereign_decision", agent_id: str = "",
        evidence_refs: tuple[str, ...] = (), derived_fact_ref: str = "",
    ) -> ActionIntentV1:
        data = dict(payload or {})
        intent = cls(
            intent_id, tenant_id, business_id, decision_id, correlation_id, action_type, channel, data,
            payload_hash=str(payload_hash or "").strip(),
            estimated_cost=_finite(data.get("estimated_cost"), "estimated_cost"),
            expected_value=_finite(data.get("expected_value"), "expected_value"),
            confidence=_finite(data.get("confidence"), "confidence"),
            reversible=data.get("reversible") if isinstance(data.get("reversible"), bool) else None,
            requested_by=requested_by, agent_id=agent_id,
            evidence_refs=evidence_refs, derived_fact_ref=derived_fact_ref,
        )
        issues = intent.validate_contract()
        if issues:
            raise ValueError(f"invalid action intent projection: {','.join(issues)}")
        return intent



@dataclass(frozen=True)
class ActionIntentV2:
    action_id: str
    intent_id: str
    tenant_id: str
    business_id: str
    decision_id: str
    correlation_id: str
    goal_id: str
    agent_id: str
    capability_target: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    expected_value: float | None = None
    estimated_cost: float | None = None
    confidence: float | None = None
    risk: Any = None
    reversibility: bool | None = None
    requested_autonomy: str | None = None
    deadline: Any = None
    channel: str = ""
    payload_hash: str = ""
    evidence_refs: tuple[str, ...] = ()
    derived_fact_ref: str = ""
    schema_version: int = 2

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _freeze(dict(self.parameters or {})))
        refs = tuple(
            dict.fromkeys(
                str(item).strip()
                for item in self.evidence_refs
                if str(item).strip()
            )
        )
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "derived_fact_ref", str(self.derived_fact_ref or "").strip())

    @property
    def action_type(self) -> str:
        return self.capability_target

    @property
    def requested_by(self) -> str:
        return self.agent_id

    @property
    def objective_name(self) -> str:
        return "profit_adjusted_growth"

    def parameters_copy(self) -> dict[str, Any]:
        return _thaw(self.parameters)

    def payload_copy(self) -> dict[str, Any]:
        return self.parameters_copy()

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "intent_id": self.intent_id,
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "decision_id": self.decision_id,
            "correlation_id": self.correlation_id,
            "goal_id": self.goal_id,
            "agent_id": self.agent_id,
            "capability_target": self.capability_target,
            "parameters": self.parameters_copy(),
            "expected_value": self.expected_value,
            "estimated_cost": self.estimated_cost,
            "confidence": self.confidence,
            "risk": self.risk,
            "reversibility": self.reversibility,
            "requested_autonomy": self.requested_autonomy,
            "deadline": self.deadline,
            "channel": self.channel,
            "payload_hash": self.payload_hash,
            "evidence_refs": list(self.evidence_refs),
            "derived_fact_ref": self.derived_fact_ref,
            "schema_version": self.schema_version,
        }

    def validate_contract(self) -> list[str]:
        required = (
            "action_id",
            "intent_id",
            "tenant_id",
            "business_id",
            "decision_id",
            "correlation_id",
            "goal_id",
            "agent_id",
            "capability_target",
            "channel",
        )
        issues = [
            f"invalid:{name}"
            for name in required
            if not str(getattr(self, name) or "").strip()
        ]
        if self.schema_version != 2:
            issues.append("invalid:schema_version")
        if self.estimated_cost is not None and self.estimated_cost < 0:
            issues.append("invalid:estimated_cost")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            issues.append("invalid:confidence")
        if len(self.payload_hash) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.payload_hash
        ):
            issues.append("invalid:payload_hash")
        return issues

    @classmethod
    def from_decision(
        cls,
        *,
        decision: Any,
        tenant_id: str,
        channel: str,
        payload_hash: str,
        evidence_refs: tuple[str, ...] = (),
        derived_fact_ref: str = "",
    ) -> ActionIntentV2:
        contract = getattr(decision, "contract_v2", None)
        if not isinstance(contract, Mapping) or int(contract.get("schema_version") or 0) != 2:
            raise ValueError("Decision v2 contract is required")
        payload = dict(getattr(decision, "payload", {}) or {})
        business_id = str(contract.get("business_id") or "").strip()
        goal_id = str(contract.get("goal_id") or "").strip()
        agent_id = str(contract.get("agent_id") or "").strip()
        decision_id = str(getattr(decision, "decision_id", "") or "").strip()
        action = str(getattr(decision, "action", "") or "").strip()
        if agent_id != str(getattr(decision, "issuer_id", "") or "").strip():
            raise ValueError("Decision v2 agent identity mismatch")
        intent = cls(
            action_id=f"action:{decision_id}",
            intent_id=f"intent:{decision_id}",
            tenant_id=str(tenant_id or "").strip(),
            business_id=business_id,
            decision_id=decision_id,
            correlation_id=str(getattr(decision, "correlation_id", "") or "").strip(),
            goal_id=goal_id,
            agent_id=agent_id,
            capability_target=str(payload.get("capability_target") or action).strip(),
            parameters=payload,
            expected_value=_finite(contract.get("expected_value"), "expected_value"),
            estimated_cost=_finite(payload.get("estimated_cost"), "estimated_cost"),
            confidence=_finite(contract.get("confidence"), "confidence"),
            risk=contract.get("risk"),
            reversibility=payload.get("reversible") if isinstance(payload.get("reversible"), bool) else None,
            requested_autonomy=(
                str(payload.get("autonomy_tier")).strip()
                if str(payload.get("autonomy_tier") or "").strip()
                else None
            ),
            deadline=(
                payload.get("deadline")
                if "deadline" in payload
                else contract.get("deadline")
            ),
            channel=str(channel or "").strip(),
            payload_hash=str(payload_hash or "").strip(),
            evidence_refs=evidence_refs,
            derived_fact_ref=derived_fact_ref,
        )
        selected_option = contract.get("selected_option")
        selected_option = dict(selected_option) if isinstance(selected_option, Mapping) else {}
        selected_id = str(selected_option.get("option_id") or "").strip()
        if selected_id and selected_id != action:
            raise ValueError("Decision v2 selected option does not match action")
        issues = intent.validate_contract()
        if issues:
            raise ValueError(f"invalid action intent v2: {','.join(issues)}")
        return intent

    @classmethod
    def from_projection(
        cls,
        *,
        action_id: str,
        intent_id: str,
        tenant_id: str,
        business_id: str,
        decision_id: str,
        correlation_id: str,
        goal_id: str,
        agent_id: str,
        capability_target: str,
        parameters: Mapping[str, Any],
        payload_hash: str,
        expected_value: object = None,
        estimated_cost: object = None,
        confidence: object = None,
        risk: Any = None,
        reversibility: bool | None = None,
        requested_autonomy: str | None = None,
        deadline: Any = None,
        channel: str = "",
        evidence_refs: tuple[str, ...] = (),
        derived_fact_ref: str = "",
    ) -> ActionIntentV2:
        intent = cls(
            action_id=str(action_id or "").strip(),
            intent_id=str(intent_id or "").strip(),
            tenant_id=str(tenant_id or "").strip(),
            business_id=str(business_id or "").strip(),
            decision_id=str(decision_id or "").strip(),
            correlation_id=str(correlation_id or "").strip(),
            goal_id=str(goal_id or "").strip(),
            agent_id=str(agent_id or "").strip(),
            capability_target=str(capability_target or "").strip(),
            parameters=parameters,
            expected_value=_finite(expected_value, "expected_value"),
            estimated_cost=_finite(estimated_cost, "estimated_cost"),
            confidence=_finite(confidence, "confidence"),
            risk=risk,
            reversibility=reversibility if isinstance(reversibility, bool) else None,
            requested_autonomy=(
                str(requested_autonomy).strip()
                if str(requested_autonomy or "").strip()
                else None
            ),
            deadline=deadline,
            channel=str(channel or "").strip(),
            payload_hash=str(payload_hash or "").strip(),
            evidence_refs=evidence_refs,
            derived_fact_ref=derived_fact_ref,
        )
        issues = intent.validate_contract()
        if issues:
            raise ValueError(f"invalid action intent v2 projection: {','.join(issues)}")
        return intent


__all__ = ["CANON_ACTION_INTENT_CONTRACT", "ActionIntentV1", "ActionIntentV2"]
