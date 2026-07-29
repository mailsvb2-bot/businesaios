from __future__ import annotations

import base64
import gzip
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = ROOT / "tools" / "agent_ruff_fix_parts"
TEMP_PATHS = (
    ROOT / ".github" / "workflows" / "agent-ruff-fix.yml",
    ROOT / "tools" / "agent_apply_ruff_fix.py",
    PARTS_DIR,
)


def main() -> None:
    encoded = "".join(
        path.read_text(encoding="ascii")
        for path in sorted(PARTS_DIR.glob("part_*.txt"))
    )
    patch = gzip.decompress(base64.b85decode(encoded.encode("ascii")))
    patch_path = ROOT / ".agent_ruff_fix.patch"
    patch_path.write_bytes(patch)
    try:
        subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=ROOT, check=True)
        subprocess.run(["git", "apply", str(patch_path)], cwd=ROOT, check=True)
    finally:
        patch_path.unlink(missing_ok=True)
    for path in TEMP_PATHS:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
