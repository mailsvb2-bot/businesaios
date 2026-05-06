from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def test_no_public_api_or_catalog_regrowth_under_collapsed_surfaces() -> None:
    forbidden_roots = [
        PROJECT_ROOT / "app" / "web",
        PROJECT_ROOT / "runtime" / "platform" / "support",
    ]
    forbidden = []
    for root in forbidden_roots:
        for path in root.rglob("public_api.py"):
            forbidden.append(path.relative_to(PROJECT_ROOT).as_posix())
        for path in root.rglob("catalog.py"):
            forbidden.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert forbidden == [], forbidden
