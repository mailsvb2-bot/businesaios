from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from contracts.action_impact_contract import CostSource
from core.safety.operational.action_spec import ActionCostPolicy

CANON_OPERATIONAL_ACTION_COST_MODEL = True


@dataclass(frozen=True)
class ActionCostResult:
    cost_minor: int
    source: CostSource


class ActionCostModel:
    def compute(self, policy: ActionCostPolicy, payload: Mapping[str, object]) -> ActionCostResult:
        policy.validate()
        normalized_payload = dict(payload or {})

        if policy.model == "none":
            return ActionCostResult(cost_minor=0, source=CostSource.NONE)
        if policy.model == "fixed":
            return ActionCostResult(
                cost_minor=max(0, int(policy.fixed_cost_minor)),
                source=CostSource.FIXED_TABLE,
            )
        if policy.model == "payload_budget":
            value = self._extract_int(normalized_payload, policy.payload_budget_key)
            return ActionCostResult(cost_minor=max(0, value), source=CostSource.DECLARED)
        if policy.model == "payload_amount":
            value = self._extract_int(normalized_payload, policy.payload_amount_key)
            return ActionCostResult(cost_minor=max(0, value), source=CostSource.DECLARED)
        if policy.model == "fixed_per_unit":
            units = self._extract_int(normalized_payload, policy.payload_unit_count_key)
            cost_minor = max(0, int(units)) * max(0, int(policy.unit_cost_minor))
            return ActionCostResult(cost_minor=cost_minor, source=CostSource.FIXED_TABLE)

        raise ValueError(f"unsupported model: {policy.model}")

    @staticmethod
    def _extract_int(payload: Mapping[str, object], key: str | None) -> int:
        if key is None:
            return 0
        raw = payload.get(key)
        if raw is None:
            return 0
        if isinstance(raw, bool):
            return int(raw)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return 0
            return int(float(text))
        raise ValueError(f"unsupported numeric payload type for key={key!r}: {type(raw).__name__}")


__all__ = [
    "ActionCostModel",
    "ActionCostResult",
]