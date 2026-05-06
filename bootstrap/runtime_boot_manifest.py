from __future__ import annotations

"""Final owner for runtime boot manifest.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells."""

CANON_RUNTIME_BOOT_MANIFEST_FINAL_OWNER = True
CANON_RUNTIME_BOOT_MANIFEST_NO_RUNTIME_ASSEMBLY = True


from typing import Final

from bootstrap.runtime_service_specs import RUNTIME_BOOT_SERVICE_SPECS

CANON_RUNTIME_BOOT_MANIFEST_INTERNAL_SUPPORT = True
CANON_RUNTIME_BOOT_MANIFEST_NO_PUBLIC_ENTRYPOINT = True
CANON_RUNTIME_BOOT_MANIFEST_DATA_ONLY = True


def _build_runtime_boot_manifest() -> tuple[dict[str, object], ...]:
    return tuple(
        spec.as_manifest_entry()
        for spec in RUNTIME_BOOT_SERVICE_SPECS
    )


RUNTIME_BOOT_MANIFEST: Final[tuple[dict[str, object], ...]] = _build_runtime_boot_manifest()
