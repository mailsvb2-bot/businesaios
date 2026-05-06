from __future__ import annotations

from ml.training.online_update import OnlineUpdate


def test_online_update_rejects_empty_observation_batch() -> None:
    result = OnlineUpdate().apply('model', [])
    assert result.ok is False
    assert result.code == 'online_update_observations_empty'
