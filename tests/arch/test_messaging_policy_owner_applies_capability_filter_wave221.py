from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'runtime/_internal/effects_actions/telegram/messaging_parts/policy.py'


def test_policy_owner_uses_capability_routing_before_execution():
    text = TARGET.read_text(encoding='utf-8')
    assert '_apply_capability_routing' in text
    assert 'MessagingCapabilityRouter' in text
    assert 'resolve_channel_health_registry' in text
    assert 'required_capabilities' in text
