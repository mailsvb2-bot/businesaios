import re
from pathlib import Path

import tests._infra.tracked_files as tracked_files_module
from tests._infra.tracked_files import tracked_files

PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ya\.[A-Za-z0-9_\-]{20,}"),
]

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".zip", ".pdf"}


def test_no_secrets_in_repo():
    root = Path(__file__).resolve().parents[2]
    bad = []
    for path in tracked_files(root):
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PATTERNS:
            if pattern.search(text):
                bad.append(str(path.relative_to(root)))
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

    monkeypatch.setattr(tracked_files_module.subprocess, "run", _git_unavailable)

    assert tracked_files(tmp_path) == (visible,)
