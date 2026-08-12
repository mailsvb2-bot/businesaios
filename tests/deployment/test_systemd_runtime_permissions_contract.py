from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_systemd_installer_normalizes_runtime_access_before_restart() -> None:
    installer = (ROOT / 'deploy/systemd/install.sh').read_text(encoding='utf-8')

    assert 'RUNTIME_USER="${RUNTIME_USER:-businesaios}"' in installer
    assert 'RUNTIME_GROUP="${RUNTIME_GROUP:-businesaios}"' in installer
    assert 'chgrp -R "$RUNTIME_GROUP" "$APP_DIR"' in installer
    assert 'chmod -R g+rX "$APP_DIR"' in installer
    assert 'runuser -u "$RUNTIME_USER" -- test -x "$PYTHON_BIN"' in installer
    assert 'runuser -u "$RUNTIME_USER" -- test -r "$RUNTIME_ACCESS_SENTINEL"' in installer

    access_index = installer.index('ensure_runtime_access\n\n# Historical deployments stored encrypted')
    migration_index = installer.index('migrate_legacy_security_state\n\nwrite_state installing')
    restart_index = installer.index('run_root systemctl restart "${CORE_UNITS[@]}"')
    assert access_index < migration_index < restart_index

    # The runtime account only needs read/traverse/execute access to code and
    # the venv. The installer must not make the application tree world-writable
    # or grant group write access as a shortcut.
    assert 'chmod -R 777' not in installer
    assert 'chmod -R a+rwx' not in installer
    assert 'chmod -R g+rwx' not in installer


def test_systemd_installer_migrates_legacy_security_state_fail_closed() -> None:
    installer = (ROOT / 'deploy/systemd/install.sh').read_text(encoding='utf-8')

    assert 'RUNTIME_DATA_DIR="${RUNTIME_DATA_DIR:-/var/lib/businesaios/runtime}"' in installer
    assert 'LEGACY_SECURITY_DIR="${LEGACY_SECURITY_DIR:-${APP_DIR}/data/security}"' in installer
    assert 'RUNTIME_SECURITY_DIR="${RUNTIME_SECURITY_DIR:-${RUNTIME_DATA_DIR}/security}"' in installer
    assert 'run_root cp -a "$LEGACY_SECURITY_DIR/." "$RUNTIME_SECURITY_DIR/"' in installer
    assert 'diff -qr "$LEGACY_SECURITY_DIR" "$RUNTIME_SECURITY_DIR"' in installer
    assert 'refusing to overwrite divergent runtime security state' in installer
    assert 'legacy security source preserved' in installer
    assert 'run_root chown -R "$RUNTIME_USER:$RUNTIME_GROUP" "$RUNTIME_SECURITY_DIR"' in installer
    assert 'run_root runuser -u "$RUNTIME_USER" -- test -w "$RUNTIME_SECURITY_DIR"' in installer

    # Migration is copy-and-verify; the legacy encrypted source remains a
    # rollback asset until production verification is complete.
    assert 'rm -rf "$LEGACY_SECURITY_DIR"' not in installer
    assert 'mv "$LEGACY_SECURITY_DIR"' not in installer


def test_systemd_services_remain_unprivileged_and_use_writable_runtime_data() -> None:
    for unit_name in ('businesaios-api.service', 'businesaios-worker.service'):
        unit = (ROOT / 'deploy/systemd' / unit_name).read_text(encoding='utf-8')
        assert 'User=businesaios' in unit
        assert 'Group=businesaios' in unit
        assert 'Environment=DATA_DIR=/var/lib/businesaios/runtime' in unit
        assert 'StateDirectory=businesaios/runtime' in unit
        assert 'ExecStartPre=/opt/businesaios/.venv/bin/python -m scripts.server.migrate_before_start' in unit


def test_production_env_declares_required_key_provider_master_key() -> None:
    prod_env = (ROOT / '.env.example.prod').read_text(encoding='utf-8')

    assert 'APP_ENV=prod' in prod_env
    assert 'DATA_DIR=/var/lib/businesaios/runtime' in prod_env
    assert 'BUSINESAIOS_KEY_PROVIDER_BACKEND=file' in prod_env
    assert 'BUSINESAIOS_SECRET_VAULT_BACKEND=file' in prod_env
    assert 'KEY_PROVIDER_BACKEND=postgres' not in prod_env
    assert 'SECRET_VAULT_BACKEND=postgres' not in prod_env
    assert 'BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64=' in prod_env
    assert 'Generate 32 cryptographically random bytes and Base64-encode them' in prod_env
