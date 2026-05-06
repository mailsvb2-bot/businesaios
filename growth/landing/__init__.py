from __future__ import annotations

import importlib
import sys
from typing import Any

CANON_GROWTH_LANDING_ALIAS_NAMESPACE = True

_ALIAS_MAP = {
    "cta_variant_builder": "growth.creative_engine",
    "form_variant_builder": "growth.creative_engine",
    "landing_ab_test_planner": "growth.creative_engine",
    "landing_copy_builder": "growth.creative_engine",
    "landing_layout_selector": "growth.creative_engine",
    "landing_page_factory": "growth.creative_engine",
    "landing_publish_service": "growth.creative_engine",
    "landing_template_registry": "growth.creative_engine",
    "local_proof_block_builder": "growth.creative_engine",
}

_PUBLIC_ATTRS = {
    "CtaVariantBuilder": ("growth.creative_engine", "CtaVariantBuilder"),
    "FormVariantBuilder": ("growth.creative_engine", "FormVariantBuilder"),
    "LandingAbTestPlanner": ("growth.creative_engine", "LandingAbTestPlanner"),
    "LandingCopyBuilder": ("growth.creative_engine", "LandingCopyBuilder"),
    "LandingLayoutSelector": ("growth.creative_engine", "LandingLayoutSelector"),
    "LandingPageFactory": ("growth.creative_engine", "LandingPageFactory"),
    "LandingPublishService": ("growth.creative_engine", "LandingPublishService"),
    "LandingTemplateRegistry": ("growth.creative_engine", "LandingTemplateRegistry"),
    "LocalProofBlockBuilder": ("growth.creative_engine", "LocalProofBlockBuilder"),
}


def _install_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target in _ALIAS_MAP.items():
        module = importlib.import_module(target)
        sys.modules[f"{__name__}.{alias_name}"] = module
        setattr(package, alias_name, module)


_install_aliases()


def __getattr__(name: str) -> Any:
    target = _PUBLIC_ATTRS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = ["CANON_GROWTH_LANDING_ALIAS_NAMESPACE", *sorted(_PUBLIC_ATTRS)]
