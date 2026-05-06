from application.effects.effect_outcome_vocabulary import normalize_outcome_payload, normalize_outcome_status, outcome_is_verified


def test_normalize_outcome_status_collapses_verified_aliases() -> None:
    assert normalize_outcome_status("accepted") == "verified"
    assert normalize_outcome_status("executed") == "verified"
    assert normalize_outcome_status("exists") == "verified"


def test_normalize_outcome_status_preserves_control_states() -> None:
    assert normalize_outcome_status("missing_external_confirmation") == "missing_external_confirmation"
    assert normalize_outcome_status("timeout", retryable=True) == "retryable"
    assert normalize_outcome_status("noop") == "skipped"


def test_normalize_outcome_payload_sets_verified_consistently() -> None:
    payload = normalize_outcome_payload({"status": "accepted"})
    assert payload["status"] == "verified"
    assert payload["verified"] is True
    assert payload["verification_status"] == "verified"
    assert payload["evidence_status"] == "verified"
    assert outcome_is_verified(payload["status"]) is True
