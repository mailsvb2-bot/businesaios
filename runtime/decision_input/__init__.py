from __future__ import annotations

"""Decision-input runtime package alias namespace."""

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "build_decision_input_contract": ("application.decision_input.decision_input_builder", "build_decision_input_contract"),
    "build_decision_core_enrichment": ("application.decisioning.decision_core_input_bridge", "build_decision_core_enrichment"),
    "accepts_keyword": ("core.utils.call_signature", "accepts_keyword"),
    "accepts_keywords": ("core.utils.call_signature", "accepts_keywords"),
    "parameters": ("core.utils.call_signature", "parameters"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    )

