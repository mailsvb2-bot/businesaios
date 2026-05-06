from __future__ import annotations

from boot.runtime_boot_manifest import RUNTIME_BOOT_MANIFEST
from boot.wiring.runtime_manifest_validator import validate_runtime_manifest
from runtime.manifest_entry import RuntimeManifestEntry


_VALIDATE_ON_LOAD = True


def load_runtime_manifest() -> tuple[RuntimeManifestEntry, ...]:
    manifest = RUNTIME_BOOT_MANIFEST
    if _VALIDATE_ON_LOAD:
        validate_runtime_manifest(manifest)
    return manifest
