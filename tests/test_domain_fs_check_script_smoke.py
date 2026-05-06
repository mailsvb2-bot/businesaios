from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_domain_fs_check_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_canon_domain_file_system.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout.lower()
