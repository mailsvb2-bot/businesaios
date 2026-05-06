from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_world_snapshot_ast_lock_script_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "check_world_snapshot_no_second_brain.py"
    completed = subprocess.run([sys.executable, str(script)], cwd=str(root), capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
