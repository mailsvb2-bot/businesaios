from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_systemd_installer_uses_canonical_venv_python() -> None:
    installer = (ROOT / "deploy/systemd/install.sh").read_text()
    bootstrap = (ROOT / "scripts/server/bootstrap_and_verify_production.sh").read_text()
    canonical = "/opt/businesaios/.venv/bin/python"
    assert 'PYTHON_BIN="${PYTHON_BIN:-${APP_DIR}/.venv/bin/python}"' in installer
    assert 'PYTHON_BIN="${PYTHON_BIN:-python3}"' not in installer
    assert 'runuser -u "$RUNTIME_USER" -- test -x "$PYTHON_BIN"' in installer
    for name in ("businesaios-api.service", "businesaios-worker.service"):
        assert canonical in (ROOT / "deploy/systemd" / name).read_text()
    assert 'PYTHON_BIN="$BUSINESAIOS_DEPLOY_ROOT/.venv/bin/python"' in bootstrap
