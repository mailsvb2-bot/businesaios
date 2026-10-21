"""Strict Telegram tenancy is explicit and never silently crosses tenants."""
from unittest.mock import patch
import pytest
from runtime.entrypoints.telegram_longpoll import _configured_telegram_tenant_id


@pytest.mark.parametrize("transport, deployment, strict, expected", [
    ("", "tenant-live", True, "tenant-live"),
    ("tenant-business-a", "tenant-live", True, "tenant-business-a"),
    ("", "", False, "default"),
    ("", "", True, None),
])
def test_telegram_tenant_binding(monkeypatch, transport, deployment, strict, expected):
    monkeypatch.setenv("TENANT_ID", transport)
    monkeypatch.setenv("SMOKE_TENANT_ID", deployment)
    with patch("governance.economic_layer_env.is_strict_mode", return_value=strict):
        if expected is None:
            with pytest.raises(RuntimeError, match="telegram_production_tenant_id_required"):
                _configured_telegram_tenant_id()
        else:
            assert _configured_telegram_tenant_id() == expected
