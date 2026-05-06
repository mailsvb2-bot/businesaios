from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'runtime/messaging_policy_alert_subscriptions/service.py'

def test_alert_subscription_service_does_not_start_own_dedup_logic() -> None:
    text = TARGET.read_text(encoding='utf-8')
    forbidden=('build_alert_notification_dedup_key','cooldown_active','AlertNotificationDedupRecord','PersistentAlertNotificationDedupStore')
    offenders=[item for item in forbidden if item in text]
    assert not offenders, offenders
