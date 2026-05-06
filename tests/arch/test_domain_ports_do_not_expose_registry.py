import inspect

from runtime.domain_ports import DecisionExecutionPort, ObservabilityPort


def test_decision_execution_port_does_not_expose_registry() -> None:
    signature = inspect.signature(DecisionExecutionPort)
    assert set(signature.parameters.keys()) == {"decision_core"}


def test_observability_port_does_not_expose_registry() -> None:
    signature = inspect.signature(ObservabilityPort)
    assert set(signature.parameters.keys()) == {"observability"}
