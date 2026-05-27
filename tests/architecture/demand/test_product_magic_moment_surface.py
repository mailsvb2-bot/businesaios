from __future__ import annotations

from pathlib import Path

ALLOWED_PRODUCT_MAGIC_MOMENT_FILES = {
    "__init__.py",
    "first_lead_detector.py",
    "magic_moment_publisher.py",
}


def test_product_magic_moment_surface_stays_small_and_non_redundant() -> None:
    package_dir = Path("product") / "magic_moment"
    assert {path.name for path in package_dir.glob("*.py")} == ALLOWED_PRODUCT_MAGIC_MOMENT_FILES


def test_product_magic_moment_publisher_stays_thin_facade() -> None:
    text = (Path("product") / "magic_moment" / "magic_moment_publisher.py").read_text(encoding="utf-8")
    assert "from demand_product.magic_moment_publisher import MagicMomentPublisher" in text
    assert "def publish(self, payload: dict) -> dict:" in text
    assert "code=str(" in text
    assert "business_id=str(" in text
