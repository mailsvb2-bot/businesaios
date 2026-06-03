from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set
from collections.abc import Iterable

from canon.module_manifests import DEFAULT_CANON_MODULE_MANIFESTS, CanonModuleManifest
from tools.canon_audit.contracts import SymbolRef


@dataclass
class ManifestRegistry:
    manifests: Dict[str, CanonModuleManifest]

    @classmethod
    def from_default_manifests(cls) -> "ManifestRegistry":
        return cls({m.module_name: m for m in DEFAULT_CANON_MODULE_MANIFESTS})

    def all(self) -> Iterable[CanonModuleManifest]:
        return self.manifests.values()

    def authority_index(self) -> Dict[str, Set[str]]:
        result: Dict[str, Set[str]] = {}
        for manifest in self.manifests.values():
            for authority in manifest.authorities:
                result.setdefault(authority.value, set()).add(manifest.module_name)
        return result

    def public_symbol_index(self) -> Dict[str, List[SymbolRef]]:
        result: Dict[str, List[SymbolRef]] = {}
        for manifest in self.manifests.values():
            for export_name, canonical_key in manifest.public_exports:
                result.setdefault(canonical_key, []).append(
                    SymbolRef(module=manifest.module_name, export_name=export_name, canonical_key=canonical_key)
                )
        return result
