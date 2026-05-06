from __future__ import annotations
CANON_BOOT_ADS_WIRING_FINAL_OWNER = True


CANON_BOOT_WIRING_ONLY = True

from dataclasses import dataclass
from typing import Any

from connectors.platform.ads.vault_env import EnvSecretVault
from interfaces.ads.base import AdsReadConnector, AdsWriteConnector
from interfaces.ads.effects_http_client import EffectsHTTPClient
from interfaces.ads.google_ads_connector import GoogleAdsConnector
from interfaces.ads.read_only_proxy import ReadOnlyAdsConnector
from interfaces.ads.read_service import AdsReadService
from interfaces.ads.registry import AdsConnectorRegistry
from interfaces.ads.token_store_adapter import AsyncTokenStoreAdapter
from runtime.actions import ACTION_ADS_APPLY_EXECUTE_V1
from runtime.ads import (
    AdsCommand,
    AdsGuardrails,
    AdsPlan,
    AdsPort,
    AdsService,
    BreakerConfig,
    BudgetGuardrails,
    CircuitBreaker,
    DailyLimits,
    EventLogSink,
    EventStoreSpendLedger,
)
from bootstrap.ads_write_gateway import AdsWriteGateway
from runtime.events import EventLog
from runtime.platform.config.env_flags import env_bool, env_csv, env_float
from runtime.platform.outbox.ads_token_store_sqlite import SqliteAdsTokenStore
from runtime.tenancy.paths import TenantPaths


@dataclass(frozen=True)
class AdsRuntime:
    read: AdsReadService
    write_gateway: AdsWriteGateway


def build_ads_runtime(*, tenant_paths: TenantPaths, event_store: Any, event_log: EventLog) -> AdsRuntime:
    """Canonical Ads wiring with a single honest connector surface.

    Only Google Ads is treated as implemented here. Other platforms stay in
    the registry as explicit not_implemented entries instead of looking real
    via connector skeleton modules.
    """

    vault = EnvSecretVault()

    token_db = tenant_paths.db_path("ads_oauth_tokens")
    sync_tokens = SqliteAdsTokenStore(token_db)
    tokens = AsyncTokenStoreAdapter(sync_tokens)

    http = EffectsHTTPClient()

    write_registry: AdsConnectorRegistry[AdsWriteConnector] = AdsConnectorRegistry()
    read_registry: AdsConnectorRegistry[AdsReadConnector] = AdsConnectorRegistry()

    google = GoogleAdsConnector(http=http, vault=vault, tokens=tokens)
    write_registry.register(google)
    read_registry.register(ReadOnlyAdsConnector(google))

    sink = EventLogSink(event_store=event_store, default_event_log=event_log)

    limits = DailyLimits(
        max_spend_total=env_float("ADS_MAX_SPEND_TOTAL", 50.0),
        max_spend_per_platform=env_float("ADS_MAX_SPEND_PER_PLATFORM", 50.0),
        max_spend_per_campaign=env_float("ADS_MAX_SPEND_PER_CAMPAIGN", 25.0),
        max_budget_increase_pct=env_float("ADS_MAX_BUDGET_INCREASE_PCT", 10.0),
        allow_creative_changes=env_bool("ADS_ALLOW_CREATIVE_CHANGES", False),
        change_window_utc_start=int(env_float("ADS_CHANGE_WINDOW_UTC_START", 6)),
        change_window_utc_end=int(env_float("ADS_CHANGE_WINDOW_UTC_END", 20)),
    )

    ledger = EventStoreSpendLedger(event_store=event_store)
    guard = BudgetGuardrails(limits=limits, ledger=ledger, sink=sink)

    writes_enabled = env_bool("ENABLE_ADS_WRITE", False)

    breaker = CircuitBreaker(
        cfg=BreakerConfig(
            window_s=int(env_float("ADS_BREAKER_WINDOW_S", 600)),
            max_failures=int(env_float("ADS_BREAKER_MAX_FAILURES", 3)),
            cooloff_s=int(env_float("ADS_BREAKER_COOLOFF_S", 900)),
        )
    )

    write_gateway = AdsWriteGateway(
        registry=write_registry,
        guardrails=guard,
        sink=sink,
        writes_enabled=writes_enabled,
        circuit_breaker=breaker,
    )

    return AdsRuntime(read=AdsReadService(registry=read_registry), write_gateway=write_gateway)


class _AdsRuntimePort(AdsPort):
    """Sync adapter for the canonical core AdsService."""

    def __init__(self, runtime: AdsRuntime) -> None:
        self._rt = runtime

    def draft_plan(self, tenant_id: str, spec: dict) -> AdsPlan:
        cmds = []
        for item in (spec or {}).get("commands", []) or []:
            try:
                cmds.append(
                    AdsCommand(
                        platform=str(item.get("platform") or ""),
                        action=str(item.get("action") or ""),
                        payload=dict(item.get("payload") or {}),
                    )
                )
            except Exception:
                continue
        notes = str((spec or {}).get("notes") or "")
        return AdsPlan(commands=cmds, notes=notes)

    def read_metrics(self, tenant_id: str, query: dict) -> dict:
        raise RuntimeError(
            "AdsRuntimePort.read_metrics() requires an async connector. "
            "Wire an async AdsReadConnector instead."
        )


def build_ads_service(ads_runtime: AdsRuntime) -> AdsService:
    g = AdsGuardrails(
        dry_run=env_bool("ADS_DRY_RUN", True),
        plan_only=env_bool("ADS_PLAN_ONLY", True),
        apply_enabled=env_bool("ADS_APPLY_ENABLED", False),
        max_daily_budget=env_float("ADS_MAX_DAILY_BUDGET", 0.0),
        allowed_platforms=env_csv("ADS_ALLOWED_PLATFORMS", ""),
    )
    return AdsService(port=_AdsRuntimePort(ads_runtime), guardrails=g)
