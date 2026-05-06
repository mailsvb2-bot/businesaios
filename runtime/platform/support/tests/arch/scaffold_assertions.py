from __future__ import annotations

from pathlib import Path


def assert_arch_scaffold(file_path: str) -> None:
    path = Path(file_path).resolve()
    repo_root = path.parents[4]
    assert repo_root.exists()
    assert (repo_root / "platform_layer").exists() or (repo_root / "tests").exists()
    assert path.name.startswith("test_")
    needle = "assert" + " True"
    assert needle not in path.read_text(encoding="utf-8")

__all__ = [
    "assert_arch_scaffold",
]
