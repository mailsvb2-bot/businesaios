from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_provider_admin_service_uses_single_owner_messaging_metadata_builder():
    path = ROOT / "application/business_autonomy/provider_admin_service.py"
    text = path.read_text(encoding="utf-8")
    assert "messaging_binding_to_metadata(messaging_binding)" in text
    assert "'required_capabilities': dict(messaging_binding.required_capabilities)" not in text
