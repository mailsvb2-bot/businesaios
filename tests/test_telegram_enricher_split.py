from pathlib import Path


def test_telegram_enricher_uses_helper_components():
    root = Path(__file__).resolve().parents[1]
    text = (root / "interfaces" / "telegram" / "read_models" / "enricher.py").read_text(encoding="utf-8")
    assert "load_pricing_suggestions" in text
    assert "load_user_profile" in text
    assert "load_admin_metrics" in text
