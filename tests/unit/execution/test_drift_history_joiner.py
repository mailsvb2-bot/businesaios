from execution.drift_history_joiner import DriftHistoryJoiner


def test_drift_history_joiner_builds_summary() -> None:
    payload = DriftHistoryJoiner().build(baseline_name='b1', history_rows=[{'a': 1}], rollback_record={'r': 1}, drift_reports=[{'severity': 'high'}, {'severity': 'low'}])
    assert payload['baseline_name'] == 'b1'
    assert payload['drift_summary']['samples'] == 2
    assert payload['drift_summary']['high_count'] == 1
