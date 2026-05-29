from __future__ import annotations

"""Telegram read-model enrichment.

Goals:
- Keep runner thin (no god-object)
- Keep reads deterministic and bounded
- Avoid repeated / double reads per update
- Provide a single place to cache windows (invalidated by event timestamp)

This module is READ-ONLY:
- It must not append events
- It must not call network
"""

import logging
import os
import time
from typing import Any, Dict, Optional

from core.observability.errors import log_exception_throttled
from core.observability.perf import AutoAccelerator, rolling_latency_summary
from interfaces.telegram.read_models.admin_access import is_superadmin, load_admin_metrics, resolve_admin_metrics
from interfaces.telegram.read_models.cache_window import CacheWindow as _CacheEntry
from interfaces.telegram.read_models.cache_window import is_cache_fresh
from interfaces.telegram.read_models.components.pricing import load_pricing_suggestions  # compatibility anchor
from interfaces.telegram.read_models.components.profile import load_user_profile  # compatibility anchor
from interfaces.telegram.read_models.user_bundle import load_user_bundle
from interfaces.telegram.read_models.world_state_runtime import build_world_state_for_chat
from kernel.world_state import WorldStateV1
from runtime.platform.config.feature_flags import FeatureFlags


def _now_ms() -> int:
    return int(time.time() * 1000)


log = logging.getLogger(__name__)


class TelegramReadModelEnricher:
    def __init__(self, *, event_store: Any, ttl_ms: int = 2000, tenant_id: str = "default"):
        self._event_store = event_store
        self._ttl_ms = int(ttl_ms)
        self._accelerator = AutoAccelerator(base_ttl_ms=int(ttl_ms))
        self._tenant_id = str(tenant_id or "default")
        self._user_cache: dict[str, _CacheEntry] = {}
        self._admin_cache: _CacheEntry | None = None

    def _latest_event_ts(self) -> int:
        try:
            if hasattr(self._event_store, "latest_event"):
                try:
                    ev = self._event_store.latest_event(tenant_id=self._tenant_id)  # type: ignore[attr-defined]
                except TypeError:
                    ev = self._event_store.latest_event()  # type: ignore[attr-defined]
                if isinstance(ev, dict) and ev.get("timestamp_ms") is not None:
                    return int(ev["timestamp_ms"])
        except Exception:
            return 0
        return 0

    def _emit_warning(self, *, user_id: str, reason: str, error: str) -> None:
        try:
            self._event_store.emit(
                event_type="telegram_enricher_warning",
                source="telegram_read_models",
                user_id=str(user_id),
                decision_id="-",
                correlation_id="-",
                payload={"reason": reason, "error": error},
            )
        except Exception as exc:
            log_exception_throttled(log, "telegram_read_model_bandit_warning_emit_failed", exc)

    def enrich_user(self, *, chat_id: str) -> dict[str, Any]:
        """Return a dict of user enrichment fields for WorldState.user.

        Cache key:
        - user_id
        - latest_event_ts (invalidation)
        - ttl_ms (window)
        """
        now_ms = _now_ms()
        try:
            if FeatureFlags.is_enabled("AUTO_ACCELERATOR"):
                ttl = self._accelerator.recommend_ttl_ms(latency_summary=rolling_latency_summary(top_n=3) or {})
                self._ttl_ms = int(ttl)
        except Exception as exc:
            log_exception_throttled(log, "telegram_read_model_auto_accelerator_failed", exc)
        latest_ts = self._latest_event_ts()
        key = str(chat_id)
        cached = self._user_cache.get(key)
        if is_cache_fresh(cached=cached, latest_ts=latest_ts, now_ms=now_ms, ttl_ms=self._ttl_ms):
            return dict(cached.value)

        bundle = load_user_bundle(
            event_store=self._event_store,
            tenant_id=str(self._tenant_id),
            user_id=key,
            event_warning=lambda reason, error: self._emit_warning(user_id=str(chat_id), reason=reason, error=error),
        )

        marketing_seed = str(os.getenv("MARKETING_SEED", "1") or "1").strip() or "1"
        is_super = is_superadmin(key)
        is_admin = bool(is_super) or ("admin" in {str(r) for r in bundle["roles"]})
        admin_metrics = resolve_admin_metrics(
            is_admin=is_admin,
            event_store=self._event_store,
            tenant_id=str(self._tenant_id),
            enrich_admin_metrics=self.enrich_admin_metrics,
        )

        value: dict[str, Any] = {
            "settings": bundle["settings"],
            "city": bundle["city"],
            "selected_tariff": bundle["selected_tariff"],
            "mood_last": bundle["mood_last"],
            "roles": bundle["roles"],
            "perms": bundle["perms"],
            "is_superadmin": bool(is_super),
            "admin_metrics": admin_metrics,
            "marketing_variants": bundle["marketing_variants"],
            "marketing_seed": marketing_seed,
            "marketing_bandit": bundle["marketing_bandit"],
            "entitlements": bundle["entitlements"],
            "payments": bundle["payments"],
            "realtime_state": bundle["realtime_state"],
            "behavior": bundle["behavior"],
            "pricing_suggestions": bundle["pricing_suggestions"],
            "autopilot_dashboard": bundle["autopilot_dashboard"],
        }

        self._user_cache[key] = _CacheEntry(value=value, latest_event_ts=latest_ts, computed_at_ms=now_ms)
        return dict(value)

    def build_world_state(
        self,
        *,
        chat_id: str,
        session: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        product: dict[str, Any] | None = None,
        economy: dict[str, Any] | None = None,
        entitlements: dict[str, Any] | None = None,
        limit: int = 800,
    ) -> WorldStateV1:
        """Canonical runtime builder for Telegram.

        Delegates to the single canonical entry point:
        latest_events(...) -> build_world_state_from_events(...) -> compat overlays.
        """
        return build_world_state_for_chat(
            event_store=self._event_store,
            chat_id=chat_id,
            tenant_id=self._tenant_id,
            session=session,
            meta=meta,
            product=product,
            economy=economy,
            entitlements=entitlements,
            limit=limit,
        )

    def enrich_admin_metrics(self) -> dict[str, Any]:
        now_ms = _now_ms()
        cached = self._admin_cache
        latest_ts = self._latest_event_ts()
        if is_cache_fresh(cached=cached, latest_ts=latest_ts, now_ms=now_ms, ttl_ms=max(500, self._ttl_ms)):
            return dict(cached.value)
        value = load_admin_metrics(event_store=self._event_store, tenant_id=self._tenant_id)
        self._admin_cache = _CacheEntry(value=value, latest_event_ts=latest_ts, computed_at_ms=now_ms)
        return dict(value)
