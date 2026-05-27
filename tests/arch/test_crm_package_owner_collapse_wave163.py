from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_crm_package_root_uses_direct_owner_map_and_public_api_is_compat_shell() -> None:
    root_text = (ROOT / "crm" / "__init__.py").read_text(encoding="utf-8")
    compat_text = (ROOT / "crm" / "public_api.py").read_text(encoding="utf-8")

    assert "CANON_CRM_ROOT_DIRECT_OWNER_EXPORTS = True" in root_text
    assert "'CrmConnectorRegistry': ('crm.registry.crm_connector_registry', 'CrmConnectorRegistry')" in root_text
    assert "'build_default_provider_catalog': ('crm.registry.crm_provider_catalog', 'build_default_provider_catalog')" in root_text
    assert "raise AttributeError" in root_text

    assert 'Compatibility shell for the canonical ``crm`` package root.' in compat_text
    assert 'importlib.import_module(CANONICAL_OWNER_CRM_PUBLIC_API)' in compat_text
    assert 'from crm.registry.crm_connector_registry import CrmConnectorRegistry' not in compat_text
