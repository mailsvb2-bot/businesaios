from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SYSTEMD_DIR = REPO_ROOT / 'deploy' / 'systemd'


def _read(name: str) -> str:
    return (SYSTEMD_DIR / name).read_text(encoding='utf-8')


def test_core_systemd_runtime_is_api_plus_worker() -> None:
    api = _read('businesaios-api.service')
    worker = _read('businesaios-worker.service')

    assert 'Environment=APP_PROFILE=api' in api
    assert 'Environment=APP_PROFILE=worker' in worker
    assert 'EnvironmentFile=/etc/businesaios/api.env' in api
    assert 'EnvironmentFile=/etc/businesaios/api.env' in worker


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
