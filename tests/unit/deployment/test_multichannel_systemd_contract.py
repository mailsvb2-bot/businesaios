from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SYSTEMD_DIR = REPO_ROOT / 'deploy' / 'systemd'


def _read(name: str) -> str:
    return (SYSTEMD_DIR / name).read_text(encoding='utf-8')


def _exec_start(unit: str) -> str:
    return next(line for line in unit.splitlines() if line.startswith('ExecStart='))


def test_core_systemd_runtime_is_api_plus_worker() -> None:
    api = _read('businesaios-api.service')
    worker = _read('businesaios-worker.service')
    guard = (REPO_ROOT / 'bootstrap' / 'prod_guards.py').read_text(encoding='utf-8')
    assert 'Environment=APP_PROFILE=api' in api
    assert 'Environment=APP_PROFILE=worker' in worker
    assert 'EnvironmentFile=/etc/businesaios/api.env' in api
    assert 'EnvironmentFile=/etc/businesaios/api.env' in worker
    assert 'ExecStart=/usr/bin/env APP_PROFILE=api /opt/businesaios/.venv/bin/python -m scripts.server.run_profile' in api
    worker_exec = _exec_start(worker)
    assert worker_exec.startswith('ExecStart=/usr/bin/env APP_PROFILE=worker ')
    assert worker_exec.endswith('/opt/businesaios/.venv/bin/python -m scripts.server.run_profile')
    for token in ('HEALTH_HOST=127.0.0.1', 'WORKER_HEALTH_PORT=8087', 'EVOLUTION_HEALTH_PORT=8087', 'EVOLUTION_ENABLED=1'):
        assert token in worker_exec
    assert "env_str('RUN_MODE', env_str('APP_PROFILE', ''))" in guard
    assert "'entrypoint_basenames': {'run_http.py', 'run_profile.py'}" in guard
    assert "'module_suffixes': {'main', 'runtime.boot.telegram_webhook_runner', 'scripts.server.run_profile'}" in guard
    assert 'def _telegram_governance_applies(profile: str) -> bool:' in guard
    assert "profile in {'telegram', 'webhook'}" in guard
    assert "profile == 'api'" in guard
    assert "'TELEGRAM_WEBHOOK_ENABLED'" in guard
    assert "'TELEGRAM_BOT_TOKEN'" not in guard


def test_all_runtime_units_use_systemd_managed_writable_state() -> None:
    for name, runtime_dir in (
        ('businesaios-api.service', 'api'),
        ('businesaios-worker.service', 'worker'),
        ('businesaios-connector-telegram.service', 'connector-telegram'),
    ):
        unit = _read(name)
        assert 'User=businesaios' in unit
        assert 'Group=businesaios' in unit
        assert 'StateDirectory=businesaios/runtime' in unit
        assert 'StateDirectoryMode=0750' in unit
        assert 'Environment=APP_RUNTIME_DATA_DIR=/var/lib/businesaios/runtime' in unit
        assert 'Environment=BAIOS_DATA_DIR=/var/lib/businesaios/runtime' in unit
        assert 'Environment=DATA_DIR=/var/lib/businesaios/runtime' in unit
        assert f'Environment=RUNTIME_DIR=/var/lib/businesaios/runtime/{runtime_dir}' in unit
        assert 'Environment=BAIOS_DATA_DIR=.runtime' not in unit


def test_installer_provisions_service_user_before_units() -> None:
    installer = _read('install.sh')
    sysusers = _read('businesaios.sysusers.conf')
    assert 'u      businesaios  -   "Runtime service"' in sysusers
    assert '/var/lib/businesaios' in sysusers
    assert '/usr/sbin/nologin' in sysusers
    assert 'run_root systemd-sysusers "$SYSUSERS_FILE"' in installer
    assert installer.index('run_root systemd-sysusers "$SYSUSERS_FILE"') < installer.index('write_state installing')
    assert installer.index('run_root systemd-sysusers "$SYSUSERS_FILE"') < installer.index('run_root systemctl enable "${CORE_UNITS[@]}"')


def test_installer_runs_directly_as_root_and_uses_sudo_only_as_fallback() -> None:
    installer = _read('install.sh')
    assert 'run_root() {' in installer
    assert 'if [[ "$(id -u)" -eq 0 ]]; then' in installer
    assert 'command -v sudo' in installer
    assert 'sudo "$@"' in installer
    assert '\nsudo install ' not in installer
    assert '\nsudo systemctl ' not in installer
    assert '\nsudo systemd-sysusers ' not in installer
    assert '\nsudo rm ' not in installer


def test_telegram_is_an_optional_connector_not_a_core_service() -> None:
    installer = _read('install.sh')
    connector = _read('businesaios-connector-telegram.service')
    assert 'CORE_UNITS=(' in installer
    assert 'businesaios-api.service' in installer
    assert 'businesaios-worker.service' in installer
    assert 'ENABLE_TELEGRAM_CONNECTOR="${ENABLE_TELEGRAM_CONNECTOR:-0}"' in installer
    assert 'Environment=APP_PROFILE=telegram' in connector
    assert 'ExecStart=/usr/bin/env APP_PROFILE=telegram /opt/businesaios/.venv/bin/python -m scripts.server.run_profile' in connector
    assert 'optional polling adapter' in connector


def test_systemd_exec_boundary_pins_profile_after_shared_environment_files() -> None:
    expected = {
        'businesaios-api.service': 'api',
        'businesaios-worker.service': 'worker',
        'businesaios-connector-telegram.service': 'telegram',
    }
    command = '/opt/businesaios/.venv/bin/python -m scripts.server.run_profile'
    for name, profile in expected.items():
        unit = _read(name)
        assert 'EnvironmentFile=/etc/businesaios/api.env' in unit
        assert f'Environment=APP_PROFILE={profile}' in unit
        exec_start = _exec_start(unit)
        assert exec_start.startswith(f'ExecStart=/usr/bin/env APP_PROFILE={profile} ')
        assert exec_start.endswith(command)
        if profile == 'worker':
            for token in ('HEALTH_HOST=127.0.0.1', 'WORKER_HEALTH_PORT=8087', 'EVOLUTION_HEALTH_PORT=8087', 'EVOLUTION_ENABLED=1'):
                assert token in exec_start


def test_legacy_telegram_centric_units_are_not_shipped() -> None:
    assert not (SYSTEMD_DIR / 'businesaios-telegram.service').exists()
    assert not (SYSTEMD_DIR / 'businesaios-evolution.service').exists()


def test_production_templates_do_not_default_to_telegram() -> None:
    for name in ('.env.prod.example', '.env.example.prod'):
        content = (REPO_ROOT / name).read_text(encoding='utf-8')
        assert 'APP_PROFILE=api' in content
        assert 'RUN_MODE=telegram' not in content
