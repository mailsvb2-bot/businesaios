from canon.action_emission_rules import ALLOWED_ACTION_EMITTERS


def test_action_emitters_are_whitelisted():
    assert 'core.ai.decision_core.DecisionCore' in ALLOWED_ACTION_EMITTERS
    assert 'execution.action_dispatcher.ActionDispatcher' in ALLOWED_ACTION_EMITTERS
