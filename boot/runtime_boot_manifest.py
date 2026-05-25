from __future__ import annotations

"""Canonical runtime boot manifest catalog.

This file is metadata only. It does not build services and does not create a
second runtime path; runtime/bootstrap/runtime_builder.py remains the internal
assembly owner.
"""

from typing import Final

from boot.runtime_service_specs import RUNTIME_SERVICE_SPECS
from runtime.manifest_entry import RuntimeManifestEntry

CANON_RUNTIME_BOOT_MANIFEST_CATALOG_OWNER: Final[bool] = True
CANON_RUNTIME_BOOT_MANIFEST_METADATA_ONLY: Final[bool] = True

RUNTIME_BOOT_MANIFEST: Final[tuple[RuntimeManifestEntry, ...]] = tuple(
    RuntimeManifestEntry(
        step_name=spec.registration_callable,
        module_path="boot.registrations",
        callable_name=spec.registration_callable,
        service_name=spec.service_name,
        service_type=spec.service_type,
        dependencies=tuple(spec.dependencies),
    )
    for spec in RUNTIME_SERVICE_SPECS
)

__all__ = [
    "CANON_RUNTIME_BOOT_MANIFEST_CATALOG_OWNER",
    "CANON_RUNTIME_BOOT_MANIFEST_METADATA_ONLY",
    "RUNTIME_BOOT_MANIFEST",
]
