from __future__ import annotations
CANON_BOOT_PHASES_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True

"""Phase functions for system boot (P00–P70).

Each function implements exactly one boot phase and returns
only what it produces. Side-effects are limited to the phase contract.
Extracted from system_builder.py.
"""

from contextlib import ExitStack
from pathlib import Path
from typing import Any

from runtime.boot import Keyring, require_signing_secret_is_safe

from runtime.events import EventLog
from runtime.platform.config.env_flags import env_path, env_str
from runtime.boot.boot_context import BootConfigError
from bootstrap.boot_helpers import _env, _mask
from bootstrap.boot_observability import emit_boot_diagnostic_lines


def boot_phase_00_build_registries():
    from runtime.actions import build_schema_registry
    from learning.registry import build_model_registry

    schemas = build_schema_registry()
    model_registry_ctx = build_model_registry()
    return schemas, model_registry_ctx


def boot_phase_10_resolve_storage_and_paths():
    """Resolve storage config and compute tenant-scoped DATA_DIR.

    Canon: all SQLite/outbox/locks live under one root:
      <DATA_DIR or repo_root/runtime/data>/<tenant_id>/
    """
    from runtime.tenancy import current_tenant_id
    from runtime.tenancy.paths import TenantPaths
    from runtime.wiring import resolve_storage_config

    storage = resolve_storage_config()
    repo_root = Path(__file__).resolve().parents[2]
    tenant_id = current_tenant_id()

    configured_root = env_path("DATA_DIR", "")
    if str(configured_root) not in {'.', ''}:
        base_root = configured_root.resolve()
    else:
        base_root = (repo_root / "runtime" / "data").resolve()

    tpaths = TenantPaths(tenant_id=tenant_id, base_root=base_root)
    base = str(tpaths.data_root)

    env = (_env("ENV", str(getattr(storage, "env", "dev"))) or "dev").lower()
    run_mode = (_env("RUN_MODE", "demo") or "demo").lower()

    return storage, repo_root, base, env, run_mode


def boot_phase_15_validate_prod_strict(env: str, run_mode: str, base: str) -> None:
    if env != "prod":
        return

    if not env_str("DATA_DIR").strip():
        raise BootConfigError("ENV=prod requires explicit DATA_DIR (absolute path recommended).")

    if run_mode == "demo":
        raise BootConfigError("ENV=prod forbids RUN_MODE=demo. Use RUN_MODE=telegram.")

    token_env = "TELEGRAM" + "_BOT" + "_TOKEN"
    if run_mode == "telegram" and not (_env(token_env) or ""):
        raise BootConfigError("ENV=prod and RUN_MODE=telegram requires the Telegram token env var to be set.")


def boot_phase_18_print_startup_diagnostics(env: str, run_mode: str, base: str) -> None:
    token_env = "TELEGRAM" + "_BOT" + "_TOKEN"
    lines = [
        "[boot] config:",
        f"[boot]   ENV={env}",
        f"[boot]   RUN_MODE={run_mode}",
        f"[boot]   DATA_DIR={base}",
        f"[boot]   {token_env}={_mask(_env(token_env))}",
    ]

    product_cfg = (_env("PRODUCT_CONFIG") or "").strip() or "organization_platform.yaml"
    active_pid = (_env("BOOT_ACTIVE_POLICY_ID") or "").strip() or "telegram_policy@v3"
    lines.append(f"[boot]   PRODUCT_CONFIG={product_cfg}")
    lines.append(f"[boot]   BOOT_ACTIVE_POLICY_ID={active_pid}")

    try:
        from runtime.platform.config.registry import CONFIG

        p = Path(__file__).resolve().parents[2] / "products" / product_cfg
        if p.exists():
            raw = CONFIG.yaml_from_path(p) or {}
            dom = str(raw.get("domain") or "").strip()
            pid = str(raw.get("product_id") or "").strip()
            if dom or pid:
                lines.append(f"[boot]   PRODUCT_ID={pid or 'unknown'}")
                lines.append(f"[boot]   PRODUCT_DOMAIN={dom or 'unknown'}")
    except Exception as exc:
        lines.append(f"[boot]   PRODUCT_CONFIG_READ_ERROR={exc}")

    emit_boot_diagnostic_lines(phase="P18", lines=lines)


def boot_phase_20_keyring(env: str) -> Keyring:
    kid = env_str("DECISION_SIGNING_KID", "k1") or "k1"
    secret_raw = env_str("DECISION_SIGNING_SECRET", "dev-secret") or "dev-secret"
    require_signing_secret_is_safe(env=env, secret_raw=secret_raw)
    return Keyring({kid: {"secret": secret_raw.encode("utf-8"), "revoked": False}}, kid)


def boot_phase_30_durable_stores(stack: ExitStack, *, base: str, storage):
    from runtime.wiring import build_durable_stores

    return build_durable_stores(stack, base_dir=base, storage=storage)


def boot_phase_40_load_settings_and_flags():
    import logging
    from runtime.platform.config.registry import CONFIG

    settings = CONFIG.settings()
    return settings, CONFIG.feature_flags(), logging


def boot_phase_50_telegram_outbound_queue(settings, event_log: EventLog, logging_mod):
    """Optional telegram outbound queue. Must be initialized BEFORE retention wiring."""
    from runtime.boot.phase_outbound import build_telegram_outbound_queue, configure_sla_budget

    telegram_outbound_queue = build_telegram_outbound_queue(
        settings=settings,
        event_log=event_log,
        logging_mod=logging_mod,
    )
    configure_sla_budget(settings=settings)
    return telegram_outbound_queue


def boot_phase_60_retention_adapter(
    *, FeatureFlags, event_store, tenant_id: str, telegram_outbound_queue, base: str, stack: ExitStack
):
    from runtime.boot.phase_retention import build_retention_adapter

    return build_retention_adapter(
        FeatureFlags=FeatureFlags,
        event_store=event_store,
        tenant_id=tenant_id,
        telegram_outbound_queue=telegram_outbound_queue,
        base=base,
        stack=stack,
    )


def boot_phase_70_policy_registry(*, settings, pricing, retention, logging_mod):
    from runtime.boot.phase_policy_registry import build_policy_registry

    return build_policy_registry(
        settings=settings,
        pricing=pricing,
        retention=retention,
        logging_mod=logging_mod,
    )
