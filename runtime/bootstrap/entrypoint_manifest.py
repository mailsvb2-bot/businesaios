from __future__ import annotations

from dataclasses import dataclass

LEGACY_BOOTSTRAP_ENTRYPOINTS: tuple[str, ...] = (
    "boot.bootstrap",
    "boot.app_public_api",
    "boot.http_public_api",
    "boot.public_api",
    "boot.runtime_public_api",
    "boot.facade",
)


@dataclass(frozen=True)
class BootstrapSurfaceManifest:
    sovereign_public_modules: tuple[str, ...]
    legacy_entrypoints: tuple[str, ...]

    def is_legacy_entrypoint(self, module_name: str) -> bool:
        normalized = str(module_name).strip()
        return normalized in self.legacy_entrypoints


_CANONICAL_MANIFEST = BootstrapSurfaceManifest(
    sovereign_public_modules=(
        "runtime.bootstrap",
        "runtime.bootstrap.sovereign_bootstrap",
    ),
    legacy_entrypoints=LEGACY_BOOTSTRAP_ENTRYPOINTS,
)


def canonical_bootstrap_surface_manifest() -> BootstrapSurfaceManifest:
    return _CANONICAL_MANIFEST


__all__ = [
    "BootstrapSurfaceManifest",
    "LEGACY_BOOTSTRAP_ENTRYPOINTS",
    "canonical_bootstrap_surface_manifest",
]
