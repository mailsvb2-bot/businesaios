from core.safety.operational.action_registry import build_default_operational_action_registry


def test_runtime_execution_actions_are_present_in_operational_registry() -> None:
    registry = build_default_operational_action_registry()
    for action_name in (
        'launch_campaign',
        'update_budget',
        'create_listing',
        'send_email',
        'rollback_action',
    ):
        assert registry.require(action_name).action_name == action_name
