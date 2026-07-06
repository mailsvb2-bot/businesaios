"""Canonical runtime package alias namespace for runtime.ai_ceo public API."""

from __future__ import annotations

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'AutonomyPolicyV1': ('core.ai_ceo', 'AutonomyPolicyV1'),
    'GrowthSnapshotV1': ('core.ai_ceo', 'GrowthSnapshotV1'),
    'build_intent': ('core.ai_ceo.intent', 'build_intent'),
    'build_plan': ('core.ai_ceo', 'build_plan'),
    'build_session_args': ('core.ai_ceo.intent', 'build_session_args'),
    'normalize_objective': ('core.ai_ceo.intent', 'normalize_objective'),
    'parse_horizon_days': ('core.ai_ceo.intent', 'parse_horizon_days'),
    'read_growth_snapshot': ('core.ai_ceo', 'read_growth_snapshot'),
    'render_plan_text': ('core.ai_ceo', 'render_plan_text'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
