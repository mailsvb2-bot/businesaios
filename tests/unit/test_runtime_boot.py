from bootstrap.compose import bootstrap_runtime


def test_bootstrap_builds_non_empty_runtime():
    orchestrator = bootstrap_runtime()
    assert len(orchestrator.services) >= 1
    assert len(orchestrator.components) >= 1
    assert orchestrator.state.ready is True
