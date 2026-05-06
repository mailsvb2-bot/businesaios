from config.telegram_settings import TelegramSettings
from config.validation import validate_telegram_settings


def test_validate_telegram_webhook_requires_url_when_auto_register_enabled():
    settings = TelegramSettings(
        bot_token='token',
        webhook_enabled=True,
        webhook_secret='secret',
        webhook_auto_register=True,
        webhook_url='',
    )
    try:
        validate_telegram_settings(settings)
    except ValueError as exc:
        assert 'TELEGRAM_WEBHOOK_URL' in str(exc)
    else:
        raise AssertionError('expected ValueError')


def test_validate_telegram_webhook_accepts_manual_registration_without_url():
    settings = TelegramSettings(
        bot_token='token',
        webhook_enabled=True,
        webhook_secret='secret',
        webhook_auto_register=False,
        webhook_url='',
        webhook_path='/telegram/webhook',
        webhook_listen_port=8080,
    )
    assert validate_telegram_settings(settings) is settings
