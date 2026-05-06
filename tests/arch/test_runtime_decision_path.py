from canon.runtime_decision_path import CANONICAL_RUNTIME_DECISION_PATH
from runtime.service_names import RuntimeServiceName
from runtime.bootstrap.runtime_builder import build_runtime


def test_decision_path_is_canonical() -> None:
    registry, _ = build_runtime()

    actual = (
        RuntimeServiceName.DECISION_CORE,
        *registry.dependencies_of(RuntimeServiceName.DECISION_CORE),
    )
    assert actual == CANONICAL_RUNTIME_DECISION_PATH
