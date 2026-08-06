from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SYSTEMD_DIR = REPO_ROOT / 'deploy' / 'systemd'
RUNTIME_DIR = '/var/lib/businesaios/runtime'


def _read(name: str) -> str:
    return (SYSTEMD_DIR / name).read_text(encoding='utf-8')


def _assert_writable_runtime_contract(unit: str) -> None:
    content = _read(unit)

    assert 'User=businesaios' in content
    assert 'Group=businesaios' in content
    assert 'StateDirectory=businesaios' in content
    assert 'StateDirectoryMode=0750' in content
    assert f'Environment=APP_RUNTIME_DATA_DIR={RUNTIME_DIR}' in content
    assert f'Environment=BUSINESAIOS_DATA_DIR={RUNTIME_DIR}' in content
    assert f'Environment=BAIOS_DATA_DIR={RUNTIME_DIR}' in content
    assert f'ExecStartPre=/usr/bin/install -d -m 0750 {RUNTIME_DIR}' in content

    # Runtime path assignments must follow EnvironmentFile so an incomplete or
    # legacy production env cannot send an unprivileged service back to
    # /opt/businesaios/.runtime.
    assert content.index('EnvironmentFile=/etc/businesaios/api.env') < content.index(
        f'Environment=APP_RUNTIME_DATA_DIR={RUNTIME_DIR}'
    )


def test_core_systemd_runtime_is_api_plus_worker() -> None:
    api = _read('businesaios-api.service')
    worker = _read('businesaios-worker.service')

    assert 'Environment=APP_PROFILE=api' in api
    assert 'Environment=APP_PROFILE=worker' in worker
    assert 'EnvironmentFile=/etc/businesaios/api.env' in api
    assert 'EnvironmentFile=/etc/businesaios/api.env' in worker


def test_all_service_profiles_have_persistent_writable_runtime_state() -> None:
    for unit in (
        'businesaios-api.service',
        'businesaios-worker.service',
        'businesaios-connector-telegram.service',
    ):
        _assert_writable_runtime_contract(unit)


def test_installer_provisions_service_identity_and_runtime_directory() -> None:
    installer = _read('install.sh')

    assert 'SERVICE_USER="${SERVICE_USER:-businesaios}"' in installer
    assert 'SERVICE_GROUP="${SERVICE_GROUP:-businesaios}"' in installer
    assert 'SERVICE_STATE_ROOT="${SERVICE_STATE_ROOT:-/var/lib/businesaios}"' in installer
    assert 'SERVICE_RUNTIME_DIR="${SERVICE_RUNTIME_DIR:-${SERVICE_STATE_ROOT}/runtime}"' in installer
    assert 'ensure_service_account()' in installer
    assert 'prepare_runtime_state()' in installer
    assert 'groupadd --system "$SERVICE_GROUP"' in installer
    assert 'useradd \\' in installer
    assert '-o "$SERVICE_USER"' in installer
    assert '-g "$SERVICE_GROUP"' in installer
    assert installer.index('ensure_service_account\n') < installer.index('write_state installing')
    assert installer.index('prepare_runtime_state\n') < installer.index('write_state installing')


def test_telegram_is_an_optional_connector_not_a_core_service() -> None:
    installer = _read('install.sh')
    connector = _read('businesaios-connector-telegram.service')

    assert 'CORE_UNITS=(' in installer
    assert 'businesaios-api.service' in installer
    assert 'businesaios-worker.service' in installer
    assert 'ENABLE_TELEGRAM_CONNECTOR="${ENABLE_TELEGRAM_CONNECTOR:-0}"' in installer
    assert 'Environment=APP_PROFILE=telegram' in connector
    assert 'optional polling adapter' in connector


def test_legacy_telegram_centric_units_are_not_shipped() -> None:
    assert not (SYSTEMD_DIR / 'businesaios-telegram.service').exists()
    assert not (SYSTEMD_DIR / 'businesaios-evolution.service').exists()


def test_production_templates_do_not_default_to_telegram() -> None:
    for name in ('.env.prod.example', '.env.example.prod'):
        content = (REPO_ROOT / name).read_text(encoding='utf-8')
        assert 'APP_PROFILE=api' in content
        assert 'RUN_MODE=telegram' not in content
