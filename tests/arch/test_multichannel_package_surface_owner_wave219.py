from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'interfaces/messaging/_shared/package_surface.py'

def test_dynamic_channel_package_surface_owner_exists_and_is_canonical():
    text=TARGET.read_text(encoding='utf-8')
    required=('CANON_CHANNEL_PACKAGE_SURFACE = True','install_channel_package_namespace','_CHANNEL_EXPORTS','make_channel_runner','make_channel_adapter','make_build_config')
    missing=[item for item in required if item not in text]
    assert not missing, missing

def test_channel_package_surface_exports_are_locked():
    text=TARGET.read_text(encoding='utf-8')
    for item in ('"Adapter"','"Runner"','"build_binding"','"build_config"','"delivery_preview"','"map_result"','"normalize_inbound"','"send_raw"','"sender_identity"'):
        assert item in text, item
