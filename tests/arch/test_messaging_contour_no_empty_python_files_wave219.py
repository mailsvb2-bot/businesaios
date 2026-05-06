from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET_ROOTS=(
    ROOT / 'interfaces/messaging',
    ROOT / 'interfaces/regional',
    ROOT / 'interfaces/web/debug/messaging_policy_snapshot',
    ROOT / 'interfaces/web/debug/messaging_policy_trace_search',
    ROOT / 'interfaces/web/debug/messaging_policy_dashboard',
    ROOT / 'interfaces/web/debug/messaging_policy_alerts',
    ROOT / 'interfaces/web/debug/messaging_policy_observability_nav',
    ROOT / 'interfaces/web/settings/alert_subscriptions',
    ROOT / 'interfaces/web/settings/alert_subscriptions_integration',
    ROOT / 'interfaces/web/settings/messaging_preferences',
    ROOT / 'interfaces/web/settings/messaging_preferences_integration',
    ROOT / 'runtime/messaging',
    ROOT / 'runtime/messaging_policy',
    ROOT / 'runtime/messaging_policy_events',
    ROOT / 'runtime/messaging_policy_readmodel',
    ROOT / 'runtime/messaging_policy_trace',
    ROOT / 'runtime/messaging_policy_dashboard',
    ROOT / 'runtime/messaging_policy_alerts',
    ROOT / 'runtime/messaging_policy_alert_subscriptions',
    ROOT / 'runtime/messaging_policy_alert_dedup',
    ROOT / 'runtime/messaging_policy_alert_dedup_persistent',
)

def test_no_empty_python_files_in_messaging_contour():
    offenders=[]
    for root in TARGET_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob('*.py'):
            if not path.read_text(encoding='utf-8').strip():
                offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, offenders
