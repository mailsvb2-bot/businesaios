"""Canonical runtime package alias namespace for runtime.explainability public API."""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'assert_non_decision_payload': ('application.decisioning.decision_output_guard', 'assert_non_decision_payload'),
    'build_creative_reasons': ('core.explainability.creative_reason_builder', 'build_creative_reasons'),
    'build_reward_reasons': ('core.explainability.reward_reason_builder', 'build_reward_reasons'),
    'to_lines': ('core.explainability.explanation_lines', 'to_lines'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
