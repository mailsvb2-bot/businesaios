from __future__ import annotations

from pathlib import Path

FORBIDDEN_DEPENDENCIES = [
    ("core", "runtime.platform"),
    ("core", "adapters"),
]


def _scan_py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "site-packages" not in str(p)]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for py in _scan_py_files(root):
        rel = py.relative_to(root)
        text = py.read_text(encoding="utf-8", errors="ignore")
        for a, b in FORBIDDEN_DEPENDENCIES:
            if str(rel).startswith(a + "/") and (f"import {b}" in text or f"from {b}" in text):
                violations.append(f"{rel}: forbidden dependency from {a} -> {b}")
    if violations:
        print("\n".join(violations))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
