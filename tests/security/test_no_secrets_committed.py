import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ya\.[A-Za-z0-9_\-]{20,}"),
]

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".zip", ".pdf"}
DELIVERY_SCAN_EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "target",
    "venv",
}


def _delivery_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if DELIVERY_SCAN_EXCLUDED_DIRS.intersection(relative.parts):
            continue
        yield path


def _tracked_files(root: Path):
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        yield from _delivery_files(root)
        return
    for raw in result.stdout.decode("utf-8", errors="ignore").split("\0"):
        if raw:
            path = root / raw
            if path.is_file():
                yield path


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


def test_delivery_scan_fallback_without_git_metadata(tmp_path, monkeypatch):
    visible = tmp_path / "runtime" / "service.py"
    ignored = tmp_path / ".venv" / "lib" / "secret.py"
    visible.parent.mkdir(parents=True)
    ignored.parent.mkdir(parents=True)
    visible.write_text("safe = True\n", encoding="utf-8")
    ignored.write_text("sk-" + ("a" * 26) + "\n", encoding="utf-8")

    def _git_unavailable(*args, **kwargs):
        raise FileNotFoundError("git unavailable")

    monkeypatch.setattr(subprocess, "run", _git_unavailable)

    assert list(_tracked_files(tmp_path)) == [visible]
