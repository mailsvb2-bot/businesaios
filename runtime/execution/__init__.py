"""Canonical runtime package alias namespace for runtime.execution public API."""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_EXECUTION_NAMESPACE = True
CANON_COMPAT_SHIM = True
CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True
CANON_PUBLIC_FACADE = True

CANON_PUBLIC_FACADE = True

_PUBLIC_ATTRS = {
    "CANON_PUBLIC_FACADE": ("runtime.execution", "CANON_PUBLIC_FACADE"),
    "DecisionCommand": ("application.decisioning.decision_command", "DecisionCommand"),
    "canonical_json_bytes": ("core.utils.canonical", "canonical_json_bytes"),
}
_ALIAS_MAP = {
    "telemetry": "runtime.observability.telemetry",
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_EXECUTION_NAMESPACE', 'CANON_COMPAT_SHIM', 'CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE', 'CANON_PUBLIC_FACADE', 'telemetry', 'CrmEffectAdapter', 'RuntimeCrmVerificationAdapter'],
    compat_alias_map=_ALIAS_MAP,
    install_public_api=True
)


class CrmEffectAdapter:
    """Tiny CRM payload adapter kept on the runtime.execution package surface."""

    def to_effect_payload(self, result: dict[str, object]) -> dict[str, object]:
        return {'effect_channel': 'crm', **dict(result)}


class RuntimeCrmVerificationAdapter:
    """Tiny CRM verification adapter kept on the runtime.execution package surface."""

    def to_execution_feedback(self, result) -> dict[str, object]:
        return {'verified': result.verified, 'record_id': result.record_id, 'reason': result.reason}
