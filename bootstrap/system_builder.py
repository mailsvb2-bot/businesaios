from __future__ import annotations


CANON_SYSTEM_BUILDER_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True


from contextlib import ExitStack

from runtime.boot.boot_context import BootConfigError, BootPhase, BootContext  # noqa: F401
from bootstrap.boot_helpers import _env, _env_float, _env_int, _env_bool, _env_csv_tuple, _mask  # noqa: F401
from bootstrap.boot_phases import (  # noqa: F401
    boot_phase_00_build_registries,
    boot_phase_10_resolve_storage_and_paths,
    boot_phase_15_validate_prod_strict,
    boot_phase_18_print_startup_diagnostics,
    boot_phase_20_keyring,
    boot_phase_30_durable_stores,
    boot_phase_40_load_settings_and_flags,
    boot_phase_50_telegram_outbound_queue,
    boot_phase_60_retention_adapter,
    boot_phase_70_policy_registry,
)
from bootstrap.handlers_wiring import wire_handlers  # noqa: F401
from runtime.boot.system_builder_parts.phase_context import initialize_boot_context
from runtime.boot.system_builder_parts.runtime_services import build_runtime_services
from bootstrap.system_builder_steps import run_product_preflight_if_any
from runtime.boot.builders.ads_stack import wire_ads_stack  # lock import for split-helper invariant

# NOTE: Product-contract boot lives in a dedicated module.
from bootstrap.product_system_builder import ProductContractSystem, SystemBuilder  # noqa: F401

from runtime.boot import PolicySelector


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_system():
    """Wire the system end-to-end (strict boot phases)."""
    from bootstrap.self_check import boot_self_check
    from runtime.boot.storage_self_check import storage_self_check
    from runtime.boot.system_builder_finalize import finalize_runtime_system
    from bootstrap.finalize_runtime_args import FinalizeRuntimeArgs

    boot_self_check()
    storage_self_check()

    preflight_system = run_product_preflight_if_any()
    if preflight_system is not None:
        return preflight_system

    ctx, model_registry_ctx, keyring = initialize_boot_context()
    stack = ExitStack()
    try:
        services = build_runtime_services(
            ctx=ctx,
            stack=stack,
            base=ctx.get_value("base"),
            storage=ctx.get_value("storage"),
            repo_root=ctx.get_value("repo_root"),
            model_registry_ctx=model_registry_ctx,
        )
        event_store = services.event_store
        composer = services.composer
        preg = services.preg
        policy_selector = PolicySelector(preg)

        ctx.self_check()

        issuer_id = str(
            getattr(getattr(services.settings, "core", None), "issuer_id", "businesaios-core")
            or "businesaios-core"
        )
        handlers = wire_handlers(ctx=ctx, event_store=event_store, composer=composer)
        core, executor, payment_outbox, stack, learning_job = finalize_runtime_system(
            args=FinalizeRuntimeArgs(
                stack=stack,
                keyring=keyring,
                schemas=ctx.get_value("schemas"),
                event_log=services.event_log,
                preg=preg,
                policy_selector=policy_selector,
                handlers=handlers,
                model_registry=model_registry_ctx,
                issuer_id=issuer_id,
                repo_root=ctx.get_value("repo_root"),
                event_store=event_store,
                base=ctx.get_value("base"),
                runtime_infra=services.runtime_infra,
            )
        )
        return core, executor, services.event_log, event_store, payment_outbox, stack, learning_job
    except Exception:
        stack.close()
        raise

