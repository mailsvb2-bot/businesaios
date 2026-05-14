from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run() -> tuple[bool, str]:
    root = Path.cwd()
    cmd = [sys.executable, "-m", "tools.architecture_bypass_scanner"]
    completed = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip()
    if completed.returncode == 0:
        return True, output or "architecture bypass scanner passed"
    message = output or "architecture bypass scanner failed"
    return False, message[:12000]
