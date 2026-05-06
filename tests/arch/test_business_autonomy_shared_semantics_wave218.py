from pathlib import Path


def test_business_autonomy_policy_uses_shared_platform_semantics() -> None:
    text = Path('application/business_autonomy/policy.py').read_text(encoding='utf-8')
    assert 'application.autonomy.autonomy_tiers' in text
    assert 'PolicySemanticsGuard' in text
    assert 'business_autonomy' in text
