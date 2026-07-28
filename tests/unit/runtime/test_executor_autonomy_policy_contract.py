from runtime.execution.executor_autonomy_policy import has_runtime_autonomy_contract


def test_empty_world_state_containers_do_not_enable_autonomy_gate() -> None:
    assert has_runtime_autonomy_contract(
        {
            "tenant_id": "tenant-a",
            "business_id": "business-a",
            "economy": {},
            "constraints": {},
            "previous_feedback": {},
        }
    ) is False


def test_explicit_non_empty_autonomy_contract_enables_gate() -> None:
    assert has_runtime_autonomy_contract(
        {
            "tenant_id": "tenant-a",
            "business_id": "business-a",
            "autonomy_tier": "supervised",
        }
    ) is True
    assert has_runtime_autonomy_contract(
        {
            "tenant_id": "tenant-a",
            "constraints": {"max_actions": 1},
        }
    ) is True
