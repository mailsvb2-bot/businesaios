"""Canonical runtime proof-registry surface.

Runtime recovery and other runtime-only flows should depend on this module
instead of importing core proof registry internals directly.
"""

from __future__ import annotations

from core.actions.proof_registry import ACTION_PROOF_EVENT
from runtime.proofs.contract import PROOF_REGISTRY_CANON, RUNTIME_PROOFS_PUBLIC_API

CANON_RUNTIME_PROOFS_PUBLIC_API = True

__all__ = [
    'CANON_RUNTIME_PROOFS_NAMESPACE',
    "ACTION_PROOF_EVENT",
    "CANON_RUNTIME_PROOFS_PUBLIC_API",
    "PROOF_REGISTRY_CANON",
    "RUNTIME_PROOFS_PUBLIC_API",
]

CANON_RUNTIME_PROOFS_NAMESPACE = True



