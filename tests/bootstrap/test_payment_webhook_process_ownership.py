from types import SimpleNamespace

import pytest

from bootstrap.assembly_runtime import validate_payments_webhook_prod_strict


def _settings():
    return SimpleNamespace(core=SimpleNamespace(env="prod", production_strict_mode=True))


def test_telegram_polling_does_not_require_yookassa_webhook_token(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "telegram")
    monkeypatch.setenv("RUN_MODE", "telegram")
    monkeypatch.delenv("YOOKASSA_WEBHOOK_TOKEN", raising=False)

    validate_payments_webhook_prod_strict(_settings())


def test_api_runtime_still_requires_yookassa_webhook_token(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.setenv("RUN_MODE", "api")
    monkeypatch.delenv("YOOKASSA_WEBHOOK_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="YOOKASSA_WEBHOOK_TOKEN"):
        validate_payments_webhook_prod_strict(_settings())
