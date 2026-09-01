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
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze(dict(self.payload or {})))

    def payload_copy(self) -> dict[str, Any]:
        return _thaw(self.payload)

    def validate_contract(self) -> list[str]:
        identity = (
            "intent_id", "tenant_id", "business_id", "decision_id",
            "correlation_id", "action_type", "channel", "requested_by",
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
        payload_hash: str, requested_by: str = "sovereign_decision",
    ) -> ActionIntentV1:
        data = dict(payload or {})
        intent = cls(
            intent_id, tenant_id, business_id, decision_id, correlation_id, action_type, channel, data,
            payload_hash=str(payload_hash or "").strip(),
            estimated_cost=_finite(data.get("estimated_cost"), "estimated_cost"),
            expected_value=_finite(data.get("expected_value"), "expected_value"),
            confidence=_finite(data.get("confidence"), "confidence"),
            reversible=data.get("reversible") if isinstance(data.get("reversible"), bool) else None,
            requested_by=requested_by,
        )
        issues = intent.validate_contract()
        if issues:
            raise ValueError(f"invalid action intent projection: {','.join(issues)}")
        return intent


__all__ = ["CANON_ACTION_INTENT_CONTRACT", "ActionIntentV1"]
