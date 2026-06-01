from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_headless_contract_canonicalizes_capability_owner_path() -> None:
    text = (ROOT / 'execution' / 'headless_contract.py').read_text(encoding='utf-8')
    assert 'self._execution_capability_router = router_candidate' in text or 'self._execution_capability_router = ExecutionCapabilityRouter' in text
    assert 'self._capability_aware_planner = CapabilityAwarePlanner(router=self._execution_capability_router)' in text
    assert 'planner_router = _planner_router(capability_aware_planner)' in text
