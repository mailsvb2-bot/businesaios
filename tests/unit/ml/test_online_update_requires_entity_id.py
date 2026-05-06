from ml.training.online_update import OnlineUpdate


def test_online_update_rejects_missing_entity_id() -> None:
    result = OnlineUpdate().apply('lead_quality_model', [{'label': 1.0}])
    assert result.ok is False
    assert result.code == 'online_update_missing_entity_id'
