"""Canonical runtime package alias namespace for runtime.enforcement public API."""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'ActionSchemaRegistry': ('core.actions.schema_registry', 'ActionSchemaRegistry'),
    'BlastRadiusPolicy': ('core.safety.blast_radius', 'BlastRadiusPolicy'),
    'WorldModelPin': ('kernel.world_model_pin', 'WorldModelPin'),
    'WorldModelPinCheckResult': ('kernel.world_model_pin', 'WorldModelPinCheckResult'),
    'allow_action': ('core.safety.blast_radius', 'allow_action'),
    'canonical_json_bytes': ('core.utils.canonical', 'canonical_json_bytes'),
    'payload_hash': ('core.utils.canonical', 'payload_hash'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
