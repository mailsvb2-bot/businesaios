import inspect

from boot.registrations.register_decision_core import RuntimeDecisionExecutionService


def test_decision_core_constructor_is_thin() -> None:
    signature = inspect.signature(RuntimeDecisionExecutionService)

    allowed = {
        "governance_chain",
        "action_executor",
        "_construction_token",
    }
    actual = set(signature.parameters.keys())

    assert actual == allowed
