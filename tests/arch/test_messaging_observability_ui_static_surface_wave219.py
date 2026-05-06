from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_STATIC=(
    'interfaces/web/settings/messaging_preferences/static/channel_preferences.css',
    'interfaces/web/settings/messaging_preferences/static/channel_preferences.js',
    'interfaces/web/settings/alert_subscriptions/static/alert_subscriptions.css',
    'interfaces/web/settings/alert_subscriptions/static/alert_subscriptions.js',
)

def test_ui_static_surfaces_exist_and_are_not_empty():
    offenders=[]
    for rel in EXPECTED_STATIC:
        path=ROOT / rel
        if not path.exists():
            offenders.append(f'missing:{rel}')
            continue
        if not path.read_text(encoding='utf-8').strip():
            offenders.append(f'empty:{rel}')
    assert not offenders, offenders
