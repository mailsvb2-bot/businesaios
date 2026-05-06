from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_provider_admin_service_uses_canonical_messaging_metadata_builder():
    path = ROOT / "application/business_autonomy/provider_admin_service.py"
    text = path.read_text(encoding="utf-8")
    assert "messaging_binding_to_metadata" in text
    assert "'messaging_binding': messaging_binding_to_metadata(messaging_binding)" in text


def test_provider_admin_service_no_duplicate_binding_resolution():
    path = ROOT / "application/business_autonomy/provider_admin_service.py"
    text = path.read_text(encoding="utf-8")
    assert text.count("messaging_binding = describe_provider_messaging_binding(provider)") == 2
