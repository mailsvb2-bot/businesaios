from __future__ import annotations

import pytest

from contracts.action_impact_contract import ActionExecutionContext
from core.safety.operational.action_registry import TELEGRAM_INTERACTIVE_ACTION_DESCRIPTORS
from core.safety.operational.factory import build_persistent_operational_safety_runtime
from runtime.boot_impl.actions_catalog import SPEC_ROWS


def _precheck(tmp_path, action: str):
    runtime = build_persistent_operational_safety_runtime(storage_path=tmp_path / "ledger.json", policy_provider=None)
    ctx = ActionExecutionContext(
        tenant_id="t1", user_id="42", action_name=action, payload={"user_id": "42"}, metadata={}, execution_id="e1"
    )
    return runtime.service.precheck(ctx)


@pytest.mark.parametrize("action", sorted(TELEGRAM_INTERACTIVE_ACTION_DESCRIPTORS))
def test_interactive_telegram_actions_pass_without_human_approval(tmp_path, action: str) -> None:
    result = _precheck(tmp_path, action)
    assert result.decision.status == "allow", result.decision.reason
    assert result.impact.requires_human_approval is False


def test_descriptors_only_name_registered_runtime_actions() -> None:
    runtime_actions = {row[0] for row in SPEC_ROWS}
    assert set(TELEGRAM_INTERACTIVE_ACTION_DESCRIPTORS) <= runtime_actions


@pytest.mark.parametrize(
    "action", ["apply_pricing_change@v1", "grant_access@v1", "create_payment_and_send_link@v1", "admin_set_role@v1"]
)
def test_money_access_and_role_actions_stay_fail_closed(tmp_path, action: str) -> None:
    assert _precheck(tmp_path, action).decision.status != "allow"



def test_policy_proposals_omit_unset_optionals_so_strict_schemas_accept_them() -> None:
    from core.actions.catalog import build_catalog
    from core.policies.telegram.helpers import propose

    proposal = propose("set_user_setting@v1", {"user_id": "u", "key": "time_work", "value": "08:30", "callback_query_id": None})
    assert "callback_query_id" not in proposal.payload
    build_catalog()["set_user_setting@v1"].schema.validate({"tenant_id": "t", **proposal.payload})
