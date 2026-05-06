from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS=[ROOT / 'runtime/messaging_policy_alert_subscriptions/settings_key.py', ROOT / 'runtime/messaging/settings.py']

def test_canonical_settings_keys_have_single_owner_files():
    expected={
        'runtime/messaging_policy_alert_subscriptions/settings_key.py': 'SETTING_KEY = "messaging_policy:alert_subscriptions"',
        'runtime/messaging/settings.py': 'SETTING_KEY = "messaging:channel_preference"',
    }
    offenders=[]
    for path in TARGETS:
        text=path.read_text(encoding='utf-8')
        rel=path.relative_to(ROOT).as_posix()
        if expected[rel] not in text:
            offenders.append(rel)
    assert not offenders, offenders
