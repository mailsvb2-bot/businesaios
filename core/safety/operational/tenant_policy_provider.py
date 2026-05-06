from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.safety.operational.operational_budget_policy import OperationalBudgetPolicy


CANON_TENANT_OPERATIONAL_POLICY_PROVIDER = True


@dataclass(frozen=True)
class TenantOperationalBudgetPolicyProvider:
    default_policy: OperationalBudgetPolicy = field(default_factory=OperationalBudgetPolicy)
    tenant_overrides: dict[str, OperationalBudgetPolicy] = field(default_factory=dict)

    def for_tenant(self, tenant_id: str) -> OperationalBudgetPolicy:
        tenant_key = str(tenant_id)
        policy = self.tenant_overrides.get(tenant_key, self.default_policy)
        policy.validate()
        return policy

    def with_override(
        self,
        tenant_id: str,
        policy: OperationalBudgetPolicy,
    ) -> "TenantOperationalBudgetPolicyProvider":
        policy.validate()
        next_overrides = dict(self.tenant_overrides)
        next_overrides[str(tenant_id)] = policy
        return TenantOperationalBudgetPolicyProvider(
            default_policy=self.default_policy,
            tenant_overrides=next_overrides,
        )

    @classmethod
    def from_mapping(
        cls,
        data: dict[str, object],
    ) -> "TenantOperationalBudgetPolicyProvider":
        raw = dict(data or {})
        default_policy = cls._policy_from_dict(dict(raw.get("default_policy") or {}))
        raw_tenant_overrides = dict(raw.get("tenant_overrides") or {})
        tenant_overrides = {
            str(tenant_id): cls._policy_from_dict(dict(policy_dict or {}))
            for tenant_id, policy_dict in raw_tenant_overrides.items()
        }
        return cls(
            default_policy=default_policy,
            tenant_overrides=tenant_overrides,
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "TenantOperationalBudgetPolicyProvider":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("policy provider JSON must be an object")
        return cls.from_mapping(payload)

    def to_dict(self) -> dict[str, object]:
        return {
            "default_policy": asdict(self.default_policy),
            "tenant_overrides": {
                tenant_id: asdict(policy)
                for tenant_id, policy in sorted(self.tenant_overrides.items())
            },
        }

    @staticmethod
    def _policy_from_dict(data: dict[str, object]) -> OperationalBudgetPolicy:
        default = OperationalBudgetPolicy()
        merged = {
            "max_actions_per_hour": data.get("max_actions_per_hour", default.max_actions_per_hour),
            "max_actions_per_day": data.get("max_actions_per_day", default.max_actions_per_day),
            "max_budget_minor_per_day": data.get("max_budget_minor_per_day", default.max_budget_minor_per_day),
            "max_new_publications_per_day": data.get(
                "max_new_publications_per_day",
                default.max_new_publications_per_day,
            ),
            "max_outbound_messages_per_day": data.get(
                "max_outbound_messages_per_day",
                default.max_outbound_messages_per_day,
            ),
            "max_strategic_changes_without_human_approval_per_day": data.get(
                "max_strategic_changes_without_human_approval_per_day",
                default.max_strategic_changes_without_human_approval_per_day,
            ),
            "max_rollback_triggers_per_day": data.get(
                "max_rollback_triggers_per_day",
                default.max_rollback_triggers_per_day,
            ),
        }
        policy = OperationalBudgetPolicy(
            max_actions_per_hour=int(merged["max_actions_per_hour"]),
            max_actions_per_day=int(merged["max_actions_per_day"]),
            max_budget_minor_per_day=int(merged["max_budget_minor_per_day"]),
            max_new_publications_per_day=int(merged["max_new_publications_per_day"]),
            max_outbound_messages_per_day=int(merged["max_outbound_messages_per_day"]),
            max_strategic_changes_without_human_approval_per_day=int(
                merged["max_strategic_changes_without_human_approval_per_day"]
            ),
            max_rollback_triggers_per_day=int(merged["max_rollback_triggers_per_day"]),
        )
        policy.validate()
        return policy


__all__ = [
    "TenantOperationalBudgetPolicyProvider",
]