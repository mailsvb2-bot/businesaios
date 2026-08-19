from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_systemd_installer_uses_canonical_venv_python() -> None:
    installer = (ROOT / "deploy/systemd/install.sh").read_text(encoding="utf-8")
    api_unit = (ROOT / "deploy/systemd/businesaios-api.service").read_text(encoding="utf-8")
    worker_unit = (ROOT / "deploy/systemd/businesaios-worker.service").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts/server/bootstrap_and_verify_production.sh").read_text(
        encoding="utf-8"
    )

    canonical_python = "/opt/businesaios/.venv/bin/python"
    assert 'PYTHON_BIN="${PYTHON_BIN:-${APP_DIR}/.venv/bin/python}"' in installer
    assert 'PYTHON_BIN="${PYTHON_BIN:-python3}"' not in installer
    assert 'runuser -u "$RUNTIME_USER" -- test -x "$PYTHON_BIN"' in installer
    assert canonical_python in api_unit
    assert canonical_python in worker_unit
    assert 'PYTHON_BIN="$BUSINESAIOS_DEPLOY_ROOT/.venv/bin/python"' in bootstrap
