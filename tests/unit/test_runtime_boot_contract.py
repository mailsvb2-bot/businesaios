from boot.runtime_boot import build_runtime_orchestrator


def test_runtime_boot_contains_required_components():
    orchestrator = build_runtime_orchestrator()
    state = orchestrator.boot()
    assert state.booted is True
    assert state.ready is True
