from __future__ import annotations

CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_TELEGRAM_BOOT_THIN_SHIM = True
CANON_TELEGRAM_BOOT_NO_RUNTIME_ASSEMBLY = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"


def boot_telegram_runner():
    from boot.app_boot_surface import build_app_boot_surface
    from interfaces.telegram.telegram_runner_integration import TelegramRunnerIntegration

    booted = build_app_boot_surface().result
    return TelegramRunnerIntegration(
        application_service=booted.decision_application,
    )
