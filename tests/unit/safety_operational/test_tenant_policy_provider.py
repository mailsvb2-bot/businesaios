from __future__ import annotations

import json
from pathlib import Path

from contracts.action_impact_contract import ActionExecutionContext
from core.safety.operational.factory import build_persistent_operational_safety_runtime
from core.safety.operational.operational_budget_policy import OperationalBudgetPolicy
from core.safety.operational.tenant_policy_provider import TenantOperationalBudgetPolicyProvider


def test_tenant_policy_provider_returns_override_when_present() -> None:
    provider = TenantOperationalBudgetPolicyProvider(
        default_policy=OperationalBudgetPolicy(max_actions_per_hour=25),
        tenant_overrides={
            "strict-tenant": OperationalBudgetPolicy(max_actions_per_hour=1),
        },
    )

    assert provider.for_tenant("strict-tenant").max_actions_per_hour == 1
    assert provider.for_tenant("other-tenant").max_actions_per_hour == 25


def test_tenant_policy_provider_can_load_from_json(tmp_path: Path) -> None:
    path = tmp_path / "tenant_policy.json"
    path.write_text(
        json.dumps(
            {
                "default_policy": {
                    "max_actions_per_hour": 10,
                    "max_actions_per_day": 100,
                },
                "tenant_overrides": {
                    "tenant-x": {
                        "max_actions_per_hour": 2,
                        "max_actions_per_day": 20,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    provider = TenantOperationalBudgetPolicyProvider.from_json_file(path)
    assert provider.for_tenant("tenant-x").max_actions_per_hour == 2
    assert provider.for_tenant("tenant-y").max_actions_per_hour == 10


def test_persistent_runtime_respects_tenant_specific_policy(tmp_path: Path) -> None:
    provider = TenantOperationalBudgetPolicyProvider(
        default_policy=OperationalBudgetPolicy(max_actions_per_hour=25),
        tenant_overrides={
            "strict-tenant": OperationalBudgetPolicy(max_actions_per_hour=1),
        },
    )
    runtime = build_persistent_operational_safety_runtime(
        storage_path=tmp_path / "runtime_ledger.json",
        policy_provider=provider,
    )

    first = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="strict-tenant",
            user_id="user-1",
            action_name="read_metrics@v1",
            execution_id="strict-1",
            payload={"safety_now": "2026-03-21T10:00:00+00:00"},
        )
    )
    assert first.decision.status == "allow"
    runtime.service.commit(first.envelope)

    second = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="strict-tenant",
            user_id="user-1",
            action_name="read_metrics@v1",
            execution_id="strict-2",
            payload={"safety_now": "2026-03-21T10:10:00+00:00"},
        )
    )
    assert second.decision.status == "block"
    assert second.decision.details["exceeded"]["max_actions_per_hour"] is True