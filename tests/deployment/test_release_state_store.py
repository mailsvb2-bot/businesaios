from __future__ import annotations

from deployment.release_state_store import DeploymentStateStore


def test_release_state_store_tracks_active_previous_and_profile(tmp_path) -> None:
    store = DeploymentStateStore(tmp_path / 'release_state.json')
    first = store.update(active_release='r1', activation_status='installed', applied_profile='systemd', last_successful_health='pending')
    assert first.active_release == 'r1'
    assert first.previous_release is None
    second = store.update(active_release='r2', activation_status='active', applied_profile='systemd', rollback_candidate='r1', last_successful_health='running')
    assert second.active_release == 'r2'
    assert second.previous_release == 'r1'
    assert second.rollback_candidate == 'r1'
    loaded = store.load()
    assert loaded.active_release == 'r2'
    assert loaded.previous_release == 'r1'
    assert loaded.last_successful_health == 'running'
    assert loaded.applied_profile == 'systemd'
