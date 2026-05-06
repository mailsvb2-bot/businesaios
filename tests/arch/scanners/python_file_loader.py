from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def iter_python_files() -> tuple[Path, ...]:
    root = project_root()
    files = []
    for path in root.rglob("*.py"):
        if ".git" in path.parts or "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        files.append(path)
    return tuple(sorted(files))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
