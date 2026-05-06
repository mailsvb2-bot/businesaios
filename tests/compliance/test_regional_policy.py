from compliance.regional_data_policy import RegionalDataPolicy


def test_unknown_region_is_denied() -> None:
    policy = RegionalDataPolicy()
    decision = policy.evaluate(source_region=None, target_region='eu', contains_pii=True)
    assert decision.allowed is False


def test_eu_to_uk_allowed_with_controls() -> None:
    policy = RegionalDataPolicy()
    decision = policy.evaluate(source_region='eu', target_region='uk', contains_pii=True, regulated=True)
    assert decision.allowed is True
    assert len(decision.required_controls) >= 1
