from __future__ import annotations

from pathlib import Path

from execution.business_memory_lock import FileBusinessMemoryLock


def test_business_memory_lock_creates_and_removes_lock_file(tmp_path: Path) -> None:
    target = tmp_path / "memory.json"
    lock_path = target.with_suffix(".json.lock")
    with FileBusinessMemoryLock(target_path=target):
        assert lock_path.exists()
    assert not lock_path.exists()
