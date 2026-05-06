from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_runtime_post_hard_lock_status_doc_exists() -> None:
    path = ROOT / "runtime" / "CANON_POST_HARD_LOCK_STATUS.md"
    text = path.read_text(encoding="utf-8")
    assert "execution-side only" in text
    assert "alternative irreversible paths" in text
