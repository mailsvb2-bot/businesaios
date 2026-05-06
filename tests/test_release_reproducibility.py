from __future__ import annotations

from pathlib import Path

def test_requirements_lock_exists():
    root = Path(__file__).resolve().parents[1]
    lock = root / "requirements.lock.txt"
    assert lock.exists(), "requirements.lock.txt must exist for reproducible builds"
    txt = lock.read_text(encoding="utf-8").strip()
    assert txt, "requirements.lock.txt must not be empty"
