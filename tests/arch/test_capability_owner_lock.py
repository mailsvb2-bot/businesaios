from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_capability_router_is_canonical_owner() -> None:
    router_text = (ROOT / 'execution' / 'capability_router.py').read_text(encoding='utf-8')
    shim_text = (ROOT / 'execution' / 'capability_aware_planning.py').read_text(encoding='utf-8')
    assert 'from execution.capability_aware_planning import' not in router_text
    assert 'CapabilityAwarePlanner' not in router_text
    assert 'from execution.capability_router import ExecutionCapabilityRouter' in shim_text
    assert 'Compatibility shim' in shim_text


def test_capability_router_depends_on_canonical_facades() -> None:
    router_text = (ROOT / 'execution' / 'capability_router.py').read_text(encoding='utf-8')
    assert 'from execution.capability_matrix import CapabilityMatrix, CapabilityRecord' in router_text
    assert 'from execution.capability_health_registry import CapabilityHealthRegistry' in router_text
    assert 'from execution.capability_diagnostics import CapabilityDiagnosticsBuilder' in router_text
