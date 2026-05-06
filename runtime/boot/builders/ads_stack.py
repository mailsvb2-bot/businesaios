from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from pathlib import Path
from typing import Any

from runtime.platform.config.env_flags import env_path
from runtime.tenancy.paths import TenantPaths
from runtime.boot.ads_wiring import build_ads_runtime, build_ads_service
from runtime.boot.builders import ads_rl as ads_rl_builder
from runtime.boot.builders import campaign_builder as campaign_builder_builder
from runtime.handlers.route_failure_support import normalized_tenant_id


def wire_ads_stack(*, tenant_id: str, repo_root: Path, event_store: Any, event_log: Any, logging_mod: Any, composer: Any) -> dict[str, Any]:
    """Build the canonical ads runtime stack.

    Returns a dict with keys:
      ads_runtime, ads, ads_rl, ads_apply_engine, campaign_builder, ads_autopilot_engine
    Missing optional pieces are returned as None, but provider wiring failures
    still raise so boot can report them explicitly.
    """
    data_root = env_path("DATA_DIR", "")
    base_root = data_root.resolve() if str(data_root) not in {'.', ''} else (repo_root / "runtime" / "data").resolve()

    effective_tenant_id = normalized_tenant_id(tenant_id, fallback="")
    tpaths = TenantPaths(tenant_id=effective_tenant_id, base_root=base_root)
    ads_runtime = build_ads_runtime(tenant_paths=tpaths, event_store=event_store, event_log=event_log)
    ads_service = build_ads_service(ads_runtime)
    logger = logging_mod.getLogger("ads_rl")
    ads_rl_service = ads_rl_builder.build_ads_rl_service(ads_service=ads_service, event_store=event_store, logger=logger)

    ads_apply_engine = None
    try:
        from runtime.boot.builders.ads_apply_engine import build_ads_apply_engine

        ads_apply_engine = build_ads_apply_engine(ads_runtime)
    except (ImportError, AttributeError, TypeError, ValueError):
        ads_apply_engine = None

    llm_client = getattr(composer, "llm_client", None) if composer else None
    campaign_builder = campaign_builder_builder.build_autopilot_campaign_builder(llm_client=llm_client)

    ads_autopilot_engine = None
    try:
        from runtime.boot.builders.ads_autopilot import build_ads_autopilot_engine

        if ads_service is not None and campaign_builder is not None:
            ads_autopilot_engine = build_ads_autopilot_engine(ads=ads_service, campaign_builder=campaign_builder)
    except (ImportError, AttributeError, TypeError, ValueError):
        ads_autopilot_engine = None

    return {
        "ads_runtime": ads_runtime,
        "ads": ads_service,
        "ads_rl": ads_rl_service,
        "ads_apply_engine": ads_apply_engine,
        "campaign_builder": campaign_builder,
        "ads_autopilot_engine": ads_autopilot_engine,
    }
