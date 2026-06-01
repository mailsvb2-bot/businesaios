from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from bootstrap.boot_phases import (
    boot_phase_00_build_registries,
    boot_phase_10_resolve_storage_and_paths,
    boot_phase_15_validate_prod_strict,
    boot_phase_18_print_startup_diagnostics,
    boot_phase_20_keyring,
)
from runtime.boot.boot_context import BootContext, BootPhase


def initialize_boot_context() -> tuple[BootContext, object, object]:
    ctx = BootContext()

    ctx.enter(BootPhase.P00_REGISTRIES)
    schemas, model_registry_ctx = boot_phase_00_build_registries()
    ctx.set_value("schemas", schemas)

    ctx.enter(BootPhase.P10_STORAGE_PATHS)
    storage, repo_root, base, env, run_mode = boot_phase_10_resolve_storage_and_paths()
    ctx.set_value("storage", storage)
    ctx.set_value("repo_root", repo_root)
    ctx.set_value("base", base)
    ctx.set_value("env", env)
    ctx.set_value("run_mode", run_mode)

    ctx.enter(BootPhase.P15_PROD_GUARDS)
    boot_phase_15_validate_prod_strict(env=env, run_mode=run_mode, base=base)

    ctx.enter(BootPhase.P18_DIAGNOSTICS)
    boot_phase_18_print_startup_diagnostics(env=env, run_mode=run_mode, base=base)

    ctx.enter(BootPhase.P20_KEYRING)
    keyring = boot_phase_20_keyring(env=env)
    ctx.set_value("keyring", keyring, min_phase=BootPhase.P20_KEYRING)
    return ctx, model_registry_ctx, keyring
