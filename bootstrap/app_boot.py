from __future__ import annotations

from bootstrap.app_boot_result import AppBootResult
from bootstrap.app_boot_surface import build_app_boot_surface

CANON_APP_BOOT_FINAL_OWNER = True
CANON_APP_BOOT_THIN_OWNER = True


def boot_application() -> AppBootResult:
    return build_app_boot_surface().result
