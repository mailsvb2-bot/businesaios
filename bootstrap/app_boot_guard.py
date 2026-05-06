from __future__ import annotations

from bootstrap.app_boot_result import AppBootResult

CANON_APP_BOOT_GUARD_FINAL_OWNER = True
CANON_APP_BOOT_GUARD_STATE_ONLY = True


def validate_app_boot_result(result: AppBootResult) -> None:
    if result.runtime is None:
        raise RuntimeError("App boot failed: runtime is missing.")
    if result.decision_application is None:
        raise RuntimeError("App boot failed: decision application service is missing.")
    if not result.startup_report:
        raise RuntimeError("App boot failed: startup report is empty.")
