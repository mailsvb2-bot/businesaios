from canon.decision_rights import DECISION_RIGHTS


def test_only_decision_core_has_decide_right():
    holders = [name for name, methods in DECISION_RIGHTS.items() if 'decide' in methods]
    assert holders == ['core.ai.decision_core.DecisionCore']
