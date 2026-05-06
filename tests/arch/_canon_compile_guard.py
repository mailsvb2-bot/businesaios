from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def python_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.py") if path.is_file())

def file_level_compile_failures() -> list[str]:
    failures: list[str] = []
    for path in python_files():
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
        except Exception:
            failures.append(str(path.relative_to(ROOT)))
    return failures
