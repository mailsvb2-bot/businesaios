from __future__ import annotations

from pathlib import Path


def test_check_locks_uses_python_bin_override_for_pytest() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "ci" / "check_locks.sh").read_text(encoding="utf-8")

    assert 'PYTHON_BIN="${PYTHON_BIN:-python}"' in script
    assert '"$PYTHON_BIN" -m pytest "${PYTEST_ARGS[@]}"' in script
    assert "\npython -m pytest " not in script
