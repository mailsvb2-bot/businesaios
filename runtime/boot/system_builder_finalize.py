from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from pathlib import Path
from typing import Any

from bootstrap.finalize_runtime_args import FinalizeRuntimeArgs
from runtime.platform.app_paths import runtime_data_dir
from runtime.platform.config.env_flags import env_path


def finalize_runtime_system(*, args: FinalizeRuntimeArgs):
    from bootstrap.world_model_self_check import run_world_model_self_check
    from runtime.boot.boot_core_assembly import build_core_assembly
    from runtime.boot.boot_ml_job import build_ml_job
    from runtime.boot.core_assembly_args import CoreAssemblyArgs
    from runtime.boot.web.runtime_web_attach import attach_runtime_web_bundle
    from runtime.platform.outbox.delivery_state import open_delivery_state

    delivery_db_path = str(env_path("DELIVERY_DB_PATH", str(runtime_data_dir() / "delivery_state.db")))
    delivery_state = args.stack.enter_context(open_delivery_state(delivery_db_path))

    asm = build_core_assembly(
        args=CoreAssemblyArgs(
            keyring=args.keyring,
            schemas=args.schemas,
            event_log=args.event_log,
            decision_archive=args.runtime_infra.decision_archive if hasattr(args.runtime_infra, 'decision_archive') else None,
            policy_registry=args.preg,
            policy_selector=args.policy_selector,
            handlers=args.handlers,
            runtime_infra=args.runtime_infra,
            delivery_state=delivery_state,
            model_registry=args.model_registry,
            issuer_id=args.issuer_id,
        )
    )
    run_world_model_self_check(world_model=asm.world_model, repo_root=args.repo_root)
    attach_runtime_web_bundle(
        runtime_obj=asm.executor,
        project_root=args.repo_root,
        settings_gateway=args.runtime_infra.settings_gateway,
        messaging_policy_read_service=args.runtime_infra.messaging_policy_read_service,
        messaging_policy_event_store=args.runtime_infra.messaging_policy_event_store,
        api_security_owner_bundle=getattr(args.runtime_infra, "api_security_owner_bundle", None),
    )

    learning_job = build_ml_job(
        event_store=args.event_store,
        core=asm.core,
        executor=asm.executor,
        policy_registry=args.preg,
        base=args.base,
    )
    return asm.core, asm.executor, args.runtime_infra.payment_outbox, args.stack, learning_job
