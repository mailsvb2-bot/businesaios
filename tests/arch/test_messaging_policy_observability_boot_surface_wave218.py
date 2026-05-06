from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_boot_observability_uses_plan_and_not_god_module_style() -> None:
    path = ROOT / 'runtime/boot/web/boot_observability.py'
    text = path.read_text(encoding='utf-8')
    assert 'execute_observability_boot_plan' in text
    assert 'ObservabilityBootArgs' in text

def test_observability_boot_plan_has_expected_flags_and_owner_fields() -> None:
    path = ROOT / 'runtime/boot/web/observability_boot_plan.py'
    text = path.read_text(encoding='utf-8')
    required=(
        'class MessagingPolicyObservabilityBootFlags',
        'navigation: bool = True',
        'snapshot: bool = True',
        'traces: bool = True',
        'dashboard: bool = True',
        'alerts: bool = True',
        'alert_subscriptions: bool = True',
        'messaging_preferences: bool = True',
        'class ObservabilityBootArgs',
        'messaging_policy_event_store',
        'messaging_policy_read_service',
    )
    missing=[item for item in required if item not in text]
    assert not missing, missing
