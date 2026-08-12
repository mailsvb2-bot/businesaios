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

    access_index = installer.index('ensure_runtime_access\n\nwrite_state installing')
    restart_index = installer.index('run_root systemctl restart "${CORE_UNITS[@]}"')
    assert access_index < restart_index

    # The runtime account only needs read/traverse/execute access to code and
    # the venv. The installer must not make the application tree world-writable
    # or grant group write access as a shortcut.
    assert 'chmod -R 777' not in installer
    assert 'chmod -R a+rwx' not in installer
    assert 'chmod -R g+rwx' not in installer


def test_systemd_services_remain_unprivileged() -> None:
    for unit_name in ('businesaios-api.service', 'businesaios-worker.service'):
        unit = (ROOT / 'deploy/systemd' / unit_name).read_text(encoding='utf-8')
        assert 'User=businesaios' in unit
        assert 'Group=businesaios' in unit
        assert 'ExecStartPre=/opt/businesaios/.venv/bin/python -m scripts.server.migrate_before_start' in unit
