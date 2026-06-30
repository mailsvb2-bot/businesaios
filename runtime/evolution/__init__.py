"""Evolution runtime package.

Runs EVOLUTION-timescale background jobs (no Telegram side-effects).
The historical ``runtime.evolution.public_api`` module is served as a package
alias so imports stay stable without keeping a second physical surface.
"""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "EvolutionOutbox": ("core.evolution.outbox", "EvolutionOutbox"),
    "handle_evolution_job": ("core.evolution.jobs", "handle_evolution_job"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    )

