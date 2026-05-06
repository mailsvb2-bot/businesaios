from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inbound_owner_lock_has_expected_canonical_entrypoints():
    text = (ROOT / 'runtime/messaging/inbound_owner_lock.py').read_text(encoding='utf-8')
    assert 'runtime.messaging.inbound_entrypoint' in text
    assert 'runtime.business_autonomy.provider_webhook_inbound_processor' in text
    assert 'interfaces.telegram.telegram_handler' not in text


def test_legacy_telegram_handler_no_longer_requires_application_service_only():
    text = (ROOT / 'interfaces/telegram/telegram_handler.py').read_text(encoding='utf-8')
    assert 'decision_core: object | None = None' in text
    assert '_handle_via_decision_core' in text
    assert 'handle_inbound_message(' in text
