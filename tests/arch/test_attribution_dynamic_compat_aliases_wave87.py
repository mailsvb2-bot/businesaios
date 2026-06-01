from __future__ import annotations

import importlib

import attribution as attribution_root
from attribution import ATTRIBUTION_COMPAT_EXPORTS, catalog


def test_attribution_root_is_thin_dynamic_facade() -> None:
    assert attribution_root.CANON_ATTRIBUTION_COMPAT_SHIM is True
    text = (
        attribution_root.__spec__.origin
        and open(attribution_root.__spec__.origin, encoding='utf-8').read()
    )
    assert '_install_compat_aliases()' in text
    assert 'ATTRIBUTION_COMPAT_EXPORTS' in text



def test_attribution_compat_modules_resolve_to_catalog_exports() -> None:
    for export_name, module_name in ATTRIBUTION_COMPAT_EXPORTS.items():
        module = importlib.import_module(f'attribution.{module_name}')
        assert getattr(module, export_name) is getattr(catalog, export_name)
        assert module.__all__ == [export_name]
        assert module.__file__.startswith('<compat:attribution.')
