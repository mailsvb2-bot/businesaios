from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_runtime_duplicate_decision_core_is_removed() -> None:
    assert not (ROOT / 'runtime/platform/support/optimization/decision_core.py').exists()


def test_runtime_duplicate_decision_trace_is_removed() -> None:
    assert not (ROOT / 'runtime/platform/support/explainability/decision_trace.py').exists()


def test_runtime_policy_registry_is_pure_core_alias() -> None:
    text = _read('runtime/platform/support/policy/policy_registry.py').strip()
    assert text == 'from core.ai.policy_registry import PolicyRegistry\n\n__all__ = ["PolicyRegistry"]'


def test_runtime_policy_factory_imports_core_registry_directly() -> None:
    text = _read('runtime/platform/support/policy/policy_factory.py')
    assert 'from core.ai.policy_registry import PolicyRegistry' in text
    assert 'runtime.platform.support.policy.policy_registry' not in text
