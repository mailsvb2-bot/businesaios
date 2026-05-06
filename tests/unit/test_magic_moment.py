from pathlib import Path

from product.magic_moment.first_lead_detector import FirstLeadDetector


def test_magic_moment_detector_returns_payload():
    result = FirstLeadDetector().detect({'lead_count': 1})
    assert result['kind'] == 'magic_moment'


def test_magic_moment_product_surface_stays_minimal():
    package_dir = Path(__file__).resolve().parents[2] / "product" / "magic_moment"
    assert {path.name for path in package_dir.glob("*.py")} == {
        "__init__.py",
        "first_lead_detector.py",
        "magic_moment_publisher.py",
    }
