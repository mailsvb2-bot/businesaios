from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _installer_text() -> str:
    return (ROOT / 'deploy/systemd/install.sh').read_text(encoding='utf-8')


def _lineage_verifier_source() -> str:
    installer = _installer_text()
    section = installer.split('verify_legacy_security_lineage() {', 1)[1]
    section = section.split('\nPY\n}\n\nmigrate_legacy_security_state()', 1)[0]
    return section.split("<<'PY'\n", 1)[1]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')


def _build_migrated_lineage_fixture(tmp_path: Path) -> tuple[Path, Path]:
    legacy = tmp_path / 'legacy'
    runtime = tmp_path / 'runtime'
    legacy.mkdir()
    runtime.mkdir()

    legacy_provider = legacy / 'key_provider.json'
    legacy_vault = legacy / 'secret_vault.json'
    _write_json(
        legacy_provider,
        {
            'records': [
                {
                    'key_id': 'legacy-key',
                    'secret_b64': 'bGVnYWN5LWtleQ==',
                }
            ]
        },
    )
    _write_json(
        legacy_vault,
        {
            'records': [],
            'keys': [
                {
                    'key_id': 'inline-key',
                    'secret_b64': 'aW5saW5lLWtleQ==',
                }
            ],
        },
    )

    _write_json(
        runtime / 'key_provider.json',
        {
            'records': [
                {
                    'key_id': 'legacy-key',
                    'wrapped_secret': 'wrapped-provider-record',
                    'key_envelope_version': 'BAIOS-KE2',
                }
            ],
            'inline_vault_key_migration': {
                'target': 'external_key_provider.BAIOS-KE2',
            },
        },
    )
    _write_json(
        runtime / 'secret_vault.json',
        {
            'records': [],
            'key_storage': 'external_key_provider',
            'inline_key_migration': {
                'target': 'external_key_provider',
            },
        },
    )

    (runtime / 'key_provider.json.legacy-secret-b64.bak').write_bytes(legacy_provider.read_bytes())
    (runtime / 'secret_vault.json.legacy-inline-keys.bak').write_bytes(legacy_vault.read_bytes())
    return legacy, runtime


def _run_lineage_verifier(legacy: Path, runtime: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        'LEGACY_SECURITY_DIR': str(legacy),
        'RUNTIME_SECURITY_DIR': str(runtime),
    }
    return subprocess.run(
        [sys.executable, '-c', _lineage_verifier_source()],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_systemd_installer_normalizes_runtime_access_before_restart() -> None:
    installer = _installer_text()

    assert 'RUNTIME_USER="${RUNTIME_USER:-businesaios}"' in installer
    assert 'RUNTIME_GROUP="${RUNTIME_GROUP:-businesaios}"' in installer
    assert 'chgrp -R "$RUNTIME_GROUP" "$APP_DIR"' in installer
    assert 'chmod -R g-w "$APP_DIR"' in installer
    assert 'chmod -R g+rX "$APP_DIR"' in installer
    assert 'find "$APP_DIR" \\( -type f -o -type d \\) -perm -g=w -print -quit' in installer
    assert 'runuser -u "$RUNTIME_USER" -- test -x "$PYTHON_BIN"' in installer
    assert 'runuser -u "$RUNTIME_USER" -- test -r "$RUNTIME_ACCESS_SENTINEL"' in installer
    assert 'runuser -u "$RUNTIME_USER" -- test -w "$RUNTIME_ACCESS_SENTINEL"' in installer

    chgrp_index = installer.index('chgrp -R "$RUNTIME_GROUP" "$APP_DIR"')
    remove_group_write_index = installer.index('chmod -R g-w "$APP_DIR"')
    add_group_read_index = installer.index('chmod -R g+rX "$APP_DIR"')
    assert chgrp_index < remove_group_write_index < add_group_read_index

    access_index = installer.index('ensure_runtime_access\n\n# Historical deployments stored encrypted')
    migration_index = installer.index('migrate_legacy_security_state\n\nwrite_state installing')
    restart_index = installer.index('run_root systemctl restart "${CORE_UNITS[@]}"')
    assert access_index < migration_index < restart_index

    # The runtime account only needs read/traverse/execute access to code and
    # the venv. The installer must remove inherited group write bits before
    # granting runtime-group access, then verify that the application tree did
    # not retain a group-writable file or directory.
    assert 'chmod -R 777' not in installer
    assert 'chmod -R a+rwx' not in installer
    assert 'chmod -R g+rwx' not in installer
    assert 'application tree still contains group-writable files or directories' in installer
    assert 'runtime user must not be able to modify application code' in installer


def test_systemd_installer_migrates_legacy_security_state_fail_closed() -> None:
    installer = _installer_text()

    assert 'RUNTIME_DATA_DIR="${RUNTIME_DATA_DIR:-/var/lib/businesaios/runtime}"' in installer
    assert 'LEGACY_SECURITY_DIR="${LEGACY_SECURITY_DIR:-${APP_DIR}/data/security}"' in installer
    assert 'RUNTIME_SECURITY_DIR="${RUNTIME_SECURITY_DIR:-${RUNTIME_DATA_DIR}/security}"' in installer
    assert 'run_root cp -a "$LEGACY_SECURITY_DIR/." "$RUNTIME_SECURITY_DIR/"' in installer
    assert 'diff -qr "$LEGACY_SECURITY_DIR" "$RUNTIME_SECURITY_DIR"' in installer
    assert 'verify_legacy_security_lineage' in installer
    assert 'key_provider.json.legacy-secret-b64.bak' in installer
    assert 'key_provider.json.pre-inline-vault-keys.bak' in installer
    assert 'secret_vault.json.legacy-inline-keys.bak' in installer
    assert 'wrapped_secret' in installer
    assert 'external_key_provider' in installer
    assert 'inline_key_migration' in installer
    assert 'unverified divergent legacy security file' in installer
    assert 'divergent runtime security state has verified migration lineage' in installer
    assert 'preserving verified migrated runtime security state' in installer
    assert 'refusing to overwrite divergent runtime security state without verified migration lineage' in installer
    assert 'legacy security source preserved' in installer
    assert 'run_root chown -R "$RUNTIME_USER:$RUNTIME_GROUP" "$RUNTIME_SECURITY_DIR"' in installer
    assert 'run_root runuser -u "$RUNTIME_USER" -- test -w "$RUNTIME_SECURITY_DIR"' in installer

    # First migration remains copy-and-verify. On later deploys, a non-empty
    # runtime may differ only as a recognized canonical migration successor:
    # every changed legacy source must match an approved rollback backup and
    # the live key/vault file must have the expected post-migration shape.
    # Unknown divergence stays fail-closed and the preserved legacy source is
    # never removed or moved out of the application tree.
    assert 'rm -rf "$LEGACY_SECURITY_DIR"' not in installer
    assert 'mv "$LEGACY_SECURITY_DIR"' not in installer


def test_security_lineage_verifier_accepts_canonical_migrated_successor(tmp_path: Path) -> None:
    legacy, runtime = _build_migrated_lineage_fixture(tmp_path)

    result = _run_lineage_verifier(legacy, runtime)

    assert result.returncode == 0, result.stderr
    assert 'verified migrated security successor key_provider.json' in result.stdout
    assert 'verified migrated security successor secret_vault.json' in result.stdout
    assert 'verified migration lineage' in result.stdout


def test_security_lineage_verifier_rejects_missing_rollback_proof(tmp_path: Path) -> None:
    legacy, runtime = _build_migrated_lineage_fixture(tmp_path)
    (runtime / 'key_provider.json.legacy-secret-b64.bak').unlink()

    result = _run_lineage_verifier(legacy, runtime)

    assert result.returncode == 1
    assert 'unverified divergent legacy security file: key_provider.json' in result.stderr


def test_security_lineage_verifier_rejects_unknown_changed_legacy_file(tmp_path: Path) -> None:
    legacy, runtime = _build_migrated_lineage_fixture(tmp_path)
    (legacy / 'unexpected-security-state.json').write_text('{"source": 1}', encoding='utf-8')
    (runtime / 'unexpected-security-state.json').write_text('{"runtime": 2}', encoding='utf-8')

    result = _run_lineage_verifier(legacy, runtime)

    assert result.returncode == 1
    assert 'unverified divergent legacy security file: unexpected-security-state.json' in result.stderr


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
