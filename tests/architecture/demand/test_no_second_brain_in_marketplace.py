from __future__ import annotations

from pathlib import Path


def test_no_second_brain_in_marketplace() -> None:
    marketplace_root = Path("marketplace")
    assert not (marketplace_root / "business_directory.py").exists()
    assert not (marketplace_root / "business_profile_store.py").exists()
    for path in marketplace_root.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "RoutingDecision(" not in src
        assert ".submit(" not in src
