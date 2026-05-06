from __future__ import annotations

import pytest

from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer


class _BootResult:
    def __init__(self) -> None:
        self.decision_application = object()


def test_fastapi_dependencies_security_storage_diagnostics(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('BUSINESAIOS_KEY_PROVIDER_BACKEND', 'sqlite')
    monkeypatch.setenv('BUSINESAIOS_SECRET_VAULT_BACKEND', 'sqlite')
    monkeypatch.setenv('BUSINESAIOS_DATA_DIR', str(tmp_path))
    container = FastAPIDependencyContainer(boot_result=_BootResult())
    diagnostics = container.security_storage_diagnostics()
    assert diagnostics['key_provider_backend'] == 'sqlite'
    assert diagnostics['secret_vault_backend'] == 'sqlite'
    assert diagnostics['shared_runtime_storage'] is True
    scheduler = container.key_rotation_scheduler()
    assert scheduler is not None


def test_fastapi_dependencies_rotation_scheduler_requires_sqlite(monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_KEY_PROVIDER_BACKEND', 'file')
    monkeypatch.setenv('BUSINESAIOS_SECRET_VAULT_BACKEND', 'file')
    container = FastAPIDependencyContainer(boot_result=_BootResult())
    with pytest.raises(RuntimeError, match='requires sqlite'):
        container.key_rotation_scheduler()


def test_fastapi_dependencies_security_storage_diagnostics_reports_actual_classes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('BUSINESAIOS_KEY_PROVIDER_BACKEND', 'sqlite')
    monkeypatch.setenv('BUSINESAIOS_SECRET_VAULT_BACKEND', 'sqlite')
    monkeypatch.setenv('BUSINESAIOS_DATA_DIR', str(tmp_path))
    container = FastAPIDependencyContainer(boot_result=_BootResult())
    diagnostics = container.security_storage_diagnostics()
    assert diagnostics['actual_key_provider_class'] == 'SqliteKeyProvider'
    assert diagnostics['actual_secret_vault_class'] == 'SqliteSecretVault'


def test_fastapi_dependencies_default_api_idempotency_path_prefers_businesaios_data_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('BUSINESAIOS_DATA_DIR', str(tmp_path / 'runtime-root'))
    container = FastAPIDependencyContainer(boot_result=_BootResult())
    path = container._default_api_idempotency_path()
    assert str(path).startswith(str(tmp_path / 'runtime-root'))
