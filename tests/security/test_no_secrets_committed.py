import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ya\.[A-Za-z0-9_\-]{20,}"),
]

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".zip", ".pdf"}


def _tracked_files(root: Path):
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    for raw in result.stdout.decode("utf-8", errors="ignore").split("\0"):
        if raw:
            yield root / raw


def test_no_secrets_in_repo():
    root = Path(__file__).resolve().parents[2]
    bad = []
    for p in _tracked_files(root):
        if p.suffix.lower() in BINARY_SUFFIXES:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for pat in PATTERNS:
            if pat.search(txt):
                bad.append(str(p.relative_to(root)))
                break
    assert not bad, f"Possible secrets detected in: {bad}"
