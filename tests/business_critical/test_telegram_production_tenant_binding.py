"""Production Telegram tenant routing must never silently choose the default tenant."""
from unittest.mock import patch

import pytest

from runtime.entrypoints.telegram_longpoll import _configured_telegram_tenant_id


def test_telegram_uses_active_deployment_tenant_if_no_override(monkeypatch):
    monkeypatch.delenv("TENANT_ID", raising=False)
    monkeypatch.setenv("SMOKE_TENANT_ID", "tenant-live")
    assert _configured_telegram_tenant_id() == "tenant-live"


def test_explicit_tenant_binding_precedes_deployment_smoke(monkeypatch):
    monkeypatch.setenv("TENANT_ID", "tenant-business-a")
    monkeypatch.setenv("SMOKE_TENANT_ID", "tenant-live")
    assert _configured_telegram_tenant_id() == "tenant-business-a"


def test_missing_production_tenant_fails_closed(monkeypatch):
    monkeypatch.delenv("TENANT_ID", raising=False)
    monkeypatch.delenv("SMOKE_TENANT_ID", raising=False)
    with patch("governance.economic_layer_env.is_strict_mode", return_value=True):
        with pytest.raises(RuntimeError, match="telegram_production_tenant_id_required"):
            _configured_telegram_tenant_id()


def test_missing_dev_tenant_preserves_legacy_default(monkeypatch):
    monkeypatch.delenv("TENANT_ID", raising=False)
    monkeypatch.delenv("SMOKE_TENANT_ID", raising=False)
    with patch("governance.economic_layer_env.is_strict_mode", return_value=False):
        assert _configured_telegram_tenant_id() == "default"
