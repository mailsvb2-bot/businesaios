from __future__ import annotations
import subprocess, sys
if __name__ == "__main__": raise SystemExit(subprocess.call([sys.executable, "scripts/ci/cli.py", "--gate", "pre-release"]))
