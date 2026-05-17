from __future__ import annotations

CANON_SYSTEM_BUILDER_STEPS_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True


import logging
from typing import Any, Dict

from bootstrap.failure_policy import raise_or_log_boot_failure
from runtime.boot.builders.ads_stack import wire_ads_stack
from runtime.boot.builders.product_preflight import run_product_preflight


LOGGER = logging.getLogger(__name__)


def _normalized_tenant_id(value: Any) -> str:
    module = __import__("runtime.handlers.route_failure_support", fromlist=["normalized_tenant_id"])
    return getattr(module, "normalized_tenant_id")(value)


def run_product_preflight_if_any() -> Any | None:
    try:
        from runtime.tenancy import current_tenant_id

        tenant_id = _normalized_tenant_id(current_tenant_id())
        if not tenant_id:
            return None
        preflight = run_product_preflight(tenant_id=tenant_id)
        if getattr(preflight, "blocked", False):
            return preflight.system
        return None
    except Exception as exc:
        raise_or_log_boot_failure(
            component="product_preflight",
            exc=exc,
            logger=LOGGER,
        )
        return None


def build_marketing_llm_components(*, settings: Any, event_store: Any, event_log: Any, logging_mod: Any) -> Dict[str, Any]:
    from runtime.boot.builders.marketing_llm import build_marketing_llm_agent, build_marketing_llm_composer

    try:
        llm_logger = logging_mod.getLogger("llm") if hasattr(logging_mod, "getLogger") else None
    except Exception as exc:
        raise_or_log_boot_failure(
            component="marketing_llm_logger",
            exc=exc,
            settings=settings,
            logger=LOGGER,
        )
        llm_logger = None

    logger = llm_logger or getattr(event_log, "logger", LOGGER)
    return {
        "marketing_llm_composer": build_marketing_llm_composer(
            settings=settings,
            event_store=event_store,
            logger=logger,
        ),
        "marketing_llm": build_marketing_llm_agent(
            settings=settings,
            event_store=event_store,
            logger=logger,
        ),
    }


def wire_ads_stack_safely(*, tenant_id: str, repo_root: Any, event_store: Any, event_log: Any, logging_mod: Any, composer: Any) -> Dict[str, Any]:
    try:
        return wire_ads_stack(
            tenant_id=tenant_id,
            repo_root=repo_root,
            event_store=event_store,
            event_log=event_log,
            logging_mod=logging_mod,
            composer=composer,
        )
    except Exception as exc:
        raise_or_log_boot_failure(
            component="ads_stack",
            exc=exc,
            logger=LOGGER,
        )
        return {
            "ads_runtime": None,
            "ads": None,
            "ads_rl": None,
            "ads_apply_engine": None,
            "campaign_builder": None,
            "ads_autopilot_engine": None,
        }
