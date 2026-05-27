from pathlib import Path

FILES = [
    'interfaces/web/settings/alert_subscriptions_integration/page_controller.py',
    'interfaces/web/settings/alert_subscriptions_integration/route_bundle.py',
    'interfaces/web/settings/alert_subscriptions_integration/save_controller.py',
    'interfaces/web/settings/alert_subscriptions_integration/static_controller.py',
]


def test_alert_subscriptions_integration_has_no_hidden_messaging_preferences_dependency() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in FILES:
        text = (root / rel).read_text(encoding='utf-8')
        assert 'messaging_preferences_integration' not in text, rel
