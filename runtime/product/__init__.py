"""Canonical runtime package alias namespace for runtime.product public API."""

from __future__ import annotations

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'ProductFeature': ('core.product.contracts', 'ProductFeature'),
    'RoadmapProposal': ('core.product.contracts', 'RoadmapProposal'),
    'RoadmapPriorityExplainer': ('core.product.explainers.roadmap_priority_explainer', 'RoadmapPriorityExplainer'),
    'build_roadmap_proposal': ('core.product.service', 'build_roadmap_proposal'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
