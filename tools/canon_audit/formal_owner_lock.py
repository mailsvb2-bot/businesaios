from __future__ import annotations

from typing import List

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.registry import ManifestRegistry


def validate_formal_owner_lock(registry: ManifestRegistry) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for canonical_key, refs in registry.public_symbol_index().items():
        if len(refs) != 1:
            violations.append(ArchitectureViolation("CANON_FORMAL_OWNER_LOCK", f"Canonical export '{canonical_key}' must have exactly one owner, got {[r.fqname for r in refs]}", canonical_key))
    for authority, owners in registry.authority_index().items():
        if len(owners) != 1:
            violations.append(ArchitectureViolation("CANON_FORMAL_AUTHORITY_LOCK", f"Authority '{authority}' must have exactly one owner, got {sorted(owners)}", authority))
    return violations
