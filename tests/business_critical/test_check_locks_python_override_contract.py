from __future__ import annotations

from pathlib import Path

from scripts.ci.subprocess_io import PYTEST_REQUIRED_PLUGINS


def test_check_locks_uses_python_bin_override_for_pytest() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "ci" / "check_locks.sh").read_text(encoding="utf-8")

    assert 'PYTHON_BIN="${PYTHON_BIN:-python}"' in script
    assert '"$PYTHON_BIN" -m pytest "${PYTEST_ARGS[@]}"' in script
    assert "\npython -m pytest " not in script


def test_check_locks_explicitly_loads_required_pytest_plugins() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "ci" / "check_locks.sh").read_text(encoding="utf-8")

    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in script
    missing = [plugin for plugin in PYTEST_REQUIRED_PLUGINS if plugin not in script]
    assert not missing, (
        "The hermetic lock shell gate must explicitly load every canonical "
        f"pytest plugin while autoload is disabled; missing={missing}"
    )
