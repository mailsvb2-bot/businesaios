from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def test_removed_connector_shells_are_gone() -> None:
    removed = [
        "interfaces/ads/catalog.py",
        "interfaces/ads/telegram_ads_connector.py",
        "interfaces/ads/vk_connector.py",
        "interfaces/ads/yandex_direct_connector.py",
        "interfaces/reviews/catalog.py",
        "interfaces/reviews/trustpilot_connector.py",
        "interfaces/reviews/yelp_reviews_connector.py",
        "interfaces/communications/catalog.py",
    ]
    for rel in removed:
        assert not (PROJECT_ROOT / rel).exists(), rel

def test_honest_registries_exist() -> None:
    assert (PROJECT_ROOT / "interfaces/ads/registry.py").exists()
    assert (PROJECT_ROOT / "interfaces/reviews/registry.py").exists()

def test_google_connectors_remain() -> None:
    assert (PROJECT_ROOT / "interfaces/ads/google_ads_connector.py").exists()
    assert (PROJECT_ROOT / "interfaces/reviews/google_reviews_connector.py").exists()
