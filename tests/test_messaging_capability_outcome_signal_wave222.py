from runtime.messaging_capability.outcome_signal import classify_delivery_outcome_signal


def test_configured_noop_is_neutral_not_measurable():
    signal = classify_delivery_outcome_signal(ok=False, meta={"mode": "configured_noop", "reason": "provider_not_enabled"})
    assert signal.measurable is False
    assert signal.mode == "configured_noop"


def test_queued_is_neutral_not_measurable():
    signal = classify_delivery_outcome_signal(ok=True, meta={"mode": "queued"})
    assert signal.measurable is False


def test_blocked_failure_is_measurable():
    signal = classify_delivery_outcome_signal(ok=False, meta={"mode": "webhook", "reason": "blocked"})
    assert signal.measurable is True
    assert signal.blocked is True
