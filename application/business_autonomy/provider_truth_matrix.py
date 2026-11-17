from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from math import isfinite
from typing import Any

from application.business_autonomy.integration_capability_catalog import CapabilityStatus, list_integration_capabilities
from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_catalog import (
    BRIDGE_MESSAGING_PROVIDER_KEYS,
    MESSAGING_GUARDED_WRITE_PROVIDER_KEYS,
    PROVIDERS,
)
from contracts.event_store import canonical_business_event_contract
from core.events.event_types import PROVIDER_CREATED, PROVIDER_LIVE_EVIDENCE, PROVIDER_UPDATED
from observability.tenant_metrics_registry import percentile_value
from runtime.business_autonomy.provider_sync_history import ProviderSyncHistory
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings

CANON_PROVIDER_TRUTH_MATRIX = True


class ProviderTruthStatus(str, Enum):
    LIVE_READY = "live_ready"
    READ_ONLY_READY = "read_only_ready"
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    CONTRACT_ONLY = "contract_only"
    NOT_IMPLEMENTED = "not_implemented"


_STATUS_RANK: Mapping[str, int] = {
    CapabilityStatus.PRODUCTION_READY.value: 6,
    CapabilityStatus.IMPLEMENTED.value: 5,
    CapabilityStatus.PARTIAL.value: 4,
    CapabilityStatus.CONTRACT_ONLY.value: 3,
    CapabilityStatus.NOT_IMPLEMENTED.value: 2,
    CapabilityStatus.NOT_FOUND.value: 1,
}
_PLACEHOLDER_TOKENS = (
    "example.invalid", ".example", "example.com", "{", "}", "configured-per-business", "vendor-configured",
    "smtp+https://provider", "https://sms-gateway.example", "https://clickhouse",
)
_PROVIDER_OWNERS: Mapping[str, str] = {
    "telegram_bot": "interfaces.messaging.telegram", "whatsapp_cloud": "interfaces.messaging.whatsapp",
    "email_connector": "interfaces.communications.email", "sms_connector": "interfaces.communications.sms",
    "call_tracking": "interfaces.communications.call_tracking", "generic_website": "interfaces.platforms.website",
    "webflow": "interfaces.platforms.webflow", "wordpress": "interfaces.platforms.wordpress",
    "shopify": "interfaces.platforms.shopify", "woocommerce": "interfaces.platforms.woocommerce",
    "amazon_marketplace": "interfaces.marketplaces.amazon", "ebay_marketplace": "interfaces.marketplaces.ebay",
    "etsy_marketplace": "interfaces.marketplaces.etsy", "wildberries_marketplace": "interfaces.marketplaces.wildberries",
    "ozon_marketplace": "interfaces.marketplaces.ozon", "hubspot": "interfaces.crm.hubspot",
    "meta_ads": "interfaces.ads.meta", "google_ads": "interfaces.ads.google", "tiktok_ads": "interfaces.ads.tiktok",
    "postgres_runtime": "infrastructure.postgres", "redis_runtime": "infrastructure.redis", "clickhouse_export": "infrastructure.clickhouse",
}
_HIGH_RISK_DOMAINS = {"ads", "marketplace", "platform_infra"}
_HIGH_RISK_PROVIDERS = {"sms_connector", "whatsapp_cloud"}
_GUARDED_WRITE_LIVE_READY: frozenset[str] = frozenset()
LIVE_EVIDENCE_CHECKS = ("credentials", "send", "receipt", "retry", "recovery")
LIVE_EVIDENCE_MAX_AGE_MS = 30 * 24 * 3600 * 1000


@dataclass(frozen=True)
class ProviderTruthRow:
    provider_key: str
    category: str
    display_name: str
    auth_scheme: str
    required_credentials: tuple[str, ...]
    read_capabilities: tuple[str, ...]
    write_capabilities: tuple[str, ...]
    status: str
    live_ready: bool
    read_only_supported: bool
    write_supported: bool
    approval_required: bool
    has_real_endpoint: bool
    has_placeholder_endpoint: bool
    endpoint_source: str
    health_requirements: tuple[str, ...]
    admin_visible: bool
    owner: str
    risk_level: str
    evidence: tuple[str, ...] = field(default_factory=tuple)
    def to_payload(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in (
            "provider_key", "category", "display_name", "auth_scheme", "status", "live_ready", "read_only_supported",
            "write_supported", "approval_required", "has_real_endpoint", "has_placeholder_endpoint", "endpoint_source",
            "admin_visible", "owner", "risk_level",
        )}
        payload.update({
            "required_credentials": list(self.required_credentials),
            "read_capabilities": list(self.read_capabilities),
            "write_capabilities": list(self.write_capabilities),
            "health_requirements": list(self.health_requirements),
            "evidence": list(self.evidence),
            "live_ready_false_reason": None if self.live_ready else self._live_ready_false_reason(),
        })
        return payload
    def _live_ready_false_reason(self) -> str:
        if self.has_placeholder_endpoint:
            return "placeholder_endpoint"
        if self.status in {ProviderTruthStatus.NOT_IMPLEMENTED.value, ProviderTruthStatus.CONTRACT_ONLY.value}:
            return self.status
        return "no_read_capability" if not self.read_only_supported else "live_readiness_not_proven"


def _required_credentials(provider: ProviderDefinition) -> tuple[str, ...]:
    return tuple(field.secret_name for field in provider.secret_fields if field.required)


def _has_placeholder_endpoint(binding: Mapping[str, Any]) -> bool:
    text = " ".join(str(binding.get(name) or "") for name in ("base_url", "probe_path", "sync_path_family")).lower()
    return any(token in text for token in _PLACEHOLDER_TOKENS)


def _has_real_endpoint(binding: Mapping[str, Any]) -> bool:
    if bool(binding.get("live_endpoint_from_secret")):
        return True
    base_url = str(binding.get("base_url") or "").strip().lower()
    return bool(base_url) and not _has_placeholder_endpoint(binding) and base_url.startswith(("https://", "postgres://", "redis://"))


_MESSAGING_ROUTE_TEMPLATE_FIELDS = frozenset({"operation", "channel_id", "ig_user_id", "page_id"})


def _truth_binding_view(provider: ProviderDefinition, binding: Mapping[str, Any]) -> dict[str, Any]:
    truth_binding = dict(binding)
    if not provider.messaging_channel:
        return truth_binding

    allowed_fields = set(_MESSAGING_ROUTE_TEMPLATE_FIELDS)
    allowed_fields.update(
        str(value).strip()
        for value in binding.get("live_required_secrets", ())
        if str(value).strip()
    )
    for key in ("probe_path", "sync_path_family"):
        text = str(truth_binding.get(key) or "")
        for field_name in sorted(allowed_fields):
            text = text.replace(f"{{{field_name}}}", field_name)
        truth_binding[key] = text
    return truth_binding


def _capability_status_by_provider() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for capability in list_integration_capabilities(include_roadmap=True):
        for provider_key in capability.provider_keys:
            result.setdefault(provider_key, []).append(capability.status.value)
    return result


def _best_capability_status(provider_key: str, status_map: Mapping[str, list[str]]) -> str:
    if provider_key in BRIDGE_MESSAGING_PROVIDER_KEYS:
        return CapabilityStatus.PARTIAL.value
    return max(status_map.get(provider_key) or [CapabilityStatus.NOT_IMPLEMENTED.value], key=lambda value: _STATUS_RANK.get(value, 0))


def _risk_level(provider: ProviderDefinition, write_capabilities: Iterable[str]) -> str:
    return "high" if provider.domain in _HIGH_RISK_DOMAINS or provider.provider_key in _HIGH_RISK_PROVIDERS else ("medium" if tuple(write_capabilities) else "low")


def _truth_status(
    *,
    capability_status: str,
    has_real_endpoint: bool,
    has_placeholder_endpoint: bool,
    read_only_supported: bool,
    write_supported: bool,
    partial_readiness_proven: bool = False,
) -> str:
    if capability_status in {CapabilityStatus.NOT_IMPLEMENTED.value, CapabilityStatus.NOT_FOUND.value}:
        return ProviderTruthStatus.NOT_IMPLEMENTED.value
    if capability_status == CapabilityStatus.CONTRACT_ONLY.value:
        return ProviderTruthStatus.CONTRACT_ONLY.value
    if has_real_endpoint and not has_placeholder_endpoint and read_only_supported:
        if capability_status == CapabilityStatus.PARTIAL.value and not partial_readiness_proven:
            return ProviderTruthStatus.PARTIAL.value
        return ProviderTruthStatus.LIVE_READY.value if write_supported else ProviderTruthStatus.READ_ONLY_READY.value
    return ProviderTruthStatus.IMPLEMENTED.value if capability_status == CapabilityStatus.IMPLEMENTED.value else ProviderTruthStatus.PARTIAL.value


def _truth_row(provider: ProviderDefinition, *, planner: ProviderSyncRuntimePlanner, bindings: ProviderTransportBindings, capability_statuses: Mapping[str, list[str]]) -> ProviderTruthRow:
    binding, plan = bindings.describe(provider), planner.describe(provider)
    read_capabilities, write_capabilities = tuple(plan.read_operations), tuple(plan.write_operations)
    required_credentials = _required_credentials(provider)
    truth_binding = _truth_binding_view(provider, binding)
    health_requirements = tuple(dict.fromkeys((*required_credentials, *tuple(str(value) for value in binding.get('live_required_secrets', ()) if str(value).strip()))))
    has_placeholder_endpoint, has_real_endpoint = _has_placeholder_endpoint(truth_binding), _has_real_endpoint(truth_binding)
    capability_status = _best_capability_status(provider.provider_key, capability_statuses)
    read_only_supported = bool(read_capabilities) and capability_status not in {CapabilityStatus.CONTRACT_ONLY.value, CapabilityStatus.NOT_IMPLEMENTED.value, CapabilityStatus.NOT_FOUND.value}
    write_supported, proven_live_write = provider.provider_key in MESSAGING_GUARDED_WRITE_PROVIDER_KEYS, provider.provider_key in (MESSAGING_GUARDED_WRITE_PROVIDER_KEYS & _GUARDED_WRITE_LIVE_READY)
    status = _truth_status(
        capability_status=capability_status,
        has_real_endpoint=has_real_endpoint,
        has_placeholder_endpoint=has_placeholder_endpoint,
        read_only_supported=read_only_supported,
        write_supported=proven_live_write,
        partial_readiness_proven=provider.provider_key in BRIDGE_MESSAGING_PROVIDER_KEYS,
    )
    live_ready = status == ProviderTruthStatus.LIVE_READY.value and bool(binding.get("live_ready")) and has_real_endpoint and not has_placeholder_endpoint and proven_live_write
    return ProviderTruthRow(
        provider_key=provider.provider_key, category=provider.domain, display_name=provider.title,
        auth_scheme=str(binding.get("auth_scheme") or "provider_secret_bundle"), required_credentials=required_credentials,
        read_capabilities=read_capabilities, write_capabilities=write_capabilities, status=status, live_ready=live_ready,
        read_only_supported=read_only_supported, write_supported=write_supported,
        approval_required=bool(write_capabilities) or provider.domain in _HIGH_RISK_DOMAINS,
        has_real_endpoint=has_real_endpoint, has_placeholder_endpoint=has_placeholder_endpoint,
        endpoint_source="runtime.business_autonomy.provider_transport_bindings", health_requirements=health_requirements,
        admin_visible=True, owner=_PROVIDER_OWNERS.get(provider.provider_key, "interfaces.messaging_runtime.channel_loader" if provider.messaging_channel else "application.business_autonomy.provider_catalog"),
        risk_level=_risk_level(provider, write_capabilities),
        evidence=(f"capability_status={capability_status}", f"transport_binding_live_ready={bool(binding.get('live_ready'))}", f"guarded_write_supported={write_supported}", f"guarded_write_live_ready={proven_live_write}"),
    )


def build_provider_truth_matrix(*, providers: Iterable[ProviderDefinition] = PROVIDERS) -> tuple[ProviderTruthRow, ...]:
    planner, bindings, statuses = ProviderSyncRuntimePlanner(), ProviderTransportBindings(), _capability_status_by_provider()
    return tuple(sorted((_truth_row(provider, planner=planner, bindings=bindings, capability_statuses=statuses) for provider in providers), key=lambda row: (row.category, row.provider_key)))


def provider_truth_map() -> dict[str, ProviderTruthRow]:
    return {row.provider_key: row for row in build_provider_truth_matrix()}


def list_provider_truth_payloads() -> list[dict[str, Any]]:
    return [row.to_payload() for row in build_provider_truth_matrix()]



def provider_runtime_truth_map(*, event_store: Any, tenant_id: str, business_id: str) -> dict[str, dict[str, Any]]:
    """Read latest provider activation truth from the canonical Event Spine."""
    tenant = str(tenant_id or "").strip()
    business = str(business_id or "").strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    if not business:
        raise ValueError("business_id is required")
    if event_store is None:
        return {}

    latest: dict[str, dict[str, Any]] = {}
    for event_type in (PROVIDER_CREATED, PROVIDER_UPDATED):
        for raw in event_store.iter_events(tenant_id=tenant, start_ms=0, event_type=event_type):
            event = canonical_business_event_contract(raw)
            if str(event.get("business_id") or "").strip() != business:
                continue
            payload = dict(event.get("payload") or {})
            provider_key = str(payload.get("provider_key") or "").strip()
            version = int(payload.get("provider_version") or 0)
            if not provider_key or version <= 0:
                raise RuntimeError("PROVIDER_ACTIVATION_EVENT_INVALID")
            candidate = {
                "provider_key": provider_key,
                "provider_version": version,
                "connected": bool(payload.get("connected")),
                "governance_enabled": bool(payload.get("governance_enabled")),
                "onboarding_ready": bool(payload.get("onboarding_ready")),
                "recorded_at_ms": int(payload.get("recorded_at_ms") or event.get("timestamp_ms") or 0),
                "health_probe": dict(payload.get("health_probe") or {}),
                "source": "event_spine.provider_activation",
            }
            current = latest.get(provider_key)
            if current is None or version > int(current["provider_version"]):
                latest[provider_key] = candidate
            elif version == int(current["provider_version"]) and candidate != current:
                raise RuntimeError("PROVIDER_ACTIVATION_EVENT_CONFLICT")
    if latest:
        # Read-only administrative visibility on the canonical tenant/business
        # provider projection. No global live write promotion occurs.
        from time import time

        evidence = provider_channel_live_readiness(
            event_store=event_store, tenant_id=tenant, business_id=business,
            now_ms=int(time() * 1000),
        )
        for provider_key, record in latest.items():
            if provider_key in evidence:
                record["channel_live_readiness"] = evidence[provider_key]
    return latest


def _provider_history_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise ValueError("provider history recorded_at_utc is invalid") from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def provider_quota_truth_map(*, quota_guard: Any, tenant_id: str, provider_keys: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Project canonical connector quota verdicts into decision-facing provider truth."""
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    if quota_guard is None:
        return {}
    providers = {provider.provider_key: provider for provider in PROVIDERS}
    result: dict[str, dict[str, Any]] = {}
    for provider_key in tuple(dict.fromkeys(str(key).strip() for key in provider_keys if str(key).strip())):
        provider = providers.get(provider_key)
        if provider is None:
            raise ValueError(f"unknown provider_key: {provider_key}")
        verdict = quota_guard.check(tenant_id=tenant, connector_id=provider.connector_id, requested_calls=1.0)
        result[provider_key] = {
            "provider_key": provider_key,
            "connector_id": provider.connector_id,
            "allowed": bool(verdict.allowed),
            "remaining": verdict.remaining,
            "reason": str(verdict.reason),
            "retry_after_seconds": verdict.retry_after_seconds,
            "source": "connector_quota_guard",
        }
    return result


def provider_runtime_metrics_truth_map(
    *,
    sync_history: ProviderSyncHistory,
    tenant_id: str,
    business_id: str,
    provider_keys: Iterable[str],
    limit: int = 50,
    window_seconds: int = 259200,
    now_utc: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Project durable provider execution history into decision-facing metrics truth."""
    tenant = str(tenant_id or "").strip()
    business = str(business_id or "").strip()
    if not tenant or not business:
        raise ValueError("tenant_id and business_id are required")
    window = int(window_seconds)
    if window <= 0:
        raise ValueError("window_seconds must be > 0")
    now = now_utc or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)
    result: dict[str, dict[str, Any]] = {}
    for provider_key in tuple(dict.fromkeys(str(key).strip() for key in provider_keys if str(key).strip())):
        rows = sync_history.list_for_provider(
            tenant_id=tenant,
            business_id=business,
            provider_key=provider_key,
            limit=max(1, int(limit)),
        )
        measured: list[dict[str, Any]] = []
        for raw_row in rows:
            row = dict(raw_row)
            raw_latency = row.get("transport_latency_ms")
            if str(row.get("mode") or "").strip().lower() != "live" or raw_latency is None:
                continue
            observed_at = _provider_history_timestamp(row.get("recorded_at_utc"))
            if observed_at is None:
                continue
            age_seconds = (now - observed_at).total_seconds()
            if age_seconds < -300:
                raise ValueError("provider history recorded_at_utc is unexpectedly in the future")
            if age_seconds > window:
                continue
            if isinstance(raw_latency, bool):
                raise ValueError("provider history transport_latency_ms must be a finite non-negative number")
            try:
                row["transport_latency_ms"] = float(raw_latency)
            except (TypeError, ValueError) as exc:
                raise ValueError("provider history transport_latency_ms must be a finite non-negative number") from exc
            if not isfinite(row["transport_latency_ms"]) or row["transport_latency_ms"] < 0.0:
                raise ValueError("provider history transport_latency_ms must be a finite non-negative number")
            row["_observed_at_utc"] = observed_at
            measured.append(row)
        if not measured:
            continue
        latencies = [float(row["transport_latency_ms"]) for row in measured]
        successes = sum(1 for row in measured if bool(row.get("accepted")))
        sample_count = len(measured)
        reliability = successes / sample_count
        result[provider_key] = {
            "provider_key": provider_key,
            "reliability": reliability,
            "error_rate": 1.0 - reliability,
            "latency_ms": percentile_value(latencies, 0.95),
            "sample_count": sample_count,
            "window_seconds": window,
            "latest_observed_at": max(row["_observed_at_utc"] for row in measured).isoformat(),
            "source": "provider_sync_history",
        }
    return result


def live_evidence_payload(*, business_id: str, provider_key: str, check: str,
                          provider_ref: str, decision_id: str, recorded_at_ms: int) -> dict[str, Any]:
    """Validated evidence schema. Caller must persist verified executor proof."""
    p = dict(business_id=str(business_id or "").strip(),
             provider_key=str(provider_key or "").strip(),
             check=str(check or "").strip(), provider_ref=str(provider_ref or "").strip(),
             decision_id=str(decision_id or "").strip(), mode="live", ok=True)
    if p["check"] not in LIVE_EVIDENCE_CHECKS or not all(
        p[k] for k in ("business_id", "provider_key", "provider_ref", "decision_id")
    ) or len(p["provider_ref"]) > 200:
        raise ValueError("provider live evidence fields are invalid")
    if type(recorded_at_ms) is not int or recorded_at_ms <= 0:
        raise ValueError("provider live evidence timestamp invalid")
    return {**p, "recorded_at_ms": recorded_at_ms}


def provider_channel_live_readiness(*, event_store: Any, tenant_id: str, business_id: str,
                                    now_ms: int, max_age_ms: int = LIVE_EVIDENCE_MAX_AGE_MS) -> dict[str, dict[str, Any]]:
    """Read-only per-tenant readiness; global guarded-write allowlist stays empty."""
    tenant, business = str(tenant_id or "").strip(), str(business_id or "").strip()
    if not tenant or not business or type(now_ms) is not int or now_ms <= 0 or type(max_age_ms) is not int or max_age_ms <= 0:
        raise ValueError("provider readiness scope/window invalid")
    seen: dict[str, dict[str, str]] = {}
    it = getattr(event_store, "iter_events", None)
    if callable(it):
        try:
            events = it(tenant_id=tenant, start_ms=now_ms - max_age_ms, end_ms=now_ms + 1,
                        event_type=PROVIDER_LIVE_EVIDENCE)
            for raw in events:
                if not isinstance(raw, Mapping) or raw.get("tenant_id") != tenant:
                    continue
                payload = raw.get("payload")
                if not isinstance(payload, Mapping):
                    continue
                try:
                    p = live_evidence_payload(
                        business_id=payload.get("business_id"), provider_key=payload.get("provider_key"),
                        check=payload.get("check"), provider_ref=payload.get("provider_ref"),
                        decision_id=payload.get("decision_id"), recorded_at_ms=payload.get("recorded_at_ms"),
                    )
                except (TypeError, ValueError):
                    continue
                if (p["business_id"] != business or payload.get("mode") != "live"
                        or payload.get("ok") is not True
                        or str(raw.get("decision_id") or "") != p["decision_id"]
                        or str(raw.get("source") or "") != "runtime.executor"
                        or not 0 <= now_ms - p["recorded_at_ms"] <= max_age_ms):
                    continue
                seen.setdefault(p["provider_key"], {})[p["check"]] = p["provider_ref"]
        except (TypeError, ValueError, RuntimeError, OSError):
            seen = {}
    rows = provider_truth_map()
    result: dict[str, dict[str, Any]] = {}
    for key in sorted(MESSAGING_GUARDED_WRITE_PROVIDER_KEYS):
        row, checks = rows.get(key), seen.get(key, {})
        endpoint_ok = bool(row is not None and row.has_real_endpoint and not row.has_placeholder_endpoint)
        missing = [name for name in LIVE_EVIDENCE_CHECKS if name not in checks]
        result[key] = {
            "provider_key": key, "live_ready": bool(endpoint_ok and not missing),
            "endpoint_ok": endpoint_ok, "missing": missing,
            "evidence": {name: checks[name] for name in LIVE_EVIDENCE_CHECKS if name in checks},
            "scope": {"tenant_id": tenant, "business_id": business},
            "source": "event_spine.provider_live_evidence",
        }
    return result


SALES_CRM_READS = ("contact_sync", "deal_sync")


def sales_source_provider_keys() -> dict[str, tuple[str, ...]]:
    """Providers that can feed the Sales Center: CRMs with contact+deal reads, messaging channels."""
    rows = provider_truth_map()
    crm = tuple(sorted(k for k, r in rows.items() if r.category == "crm" and r.read_only_supported
                       and set(SALES_CRM_READS) <= set(r.read_capabilities)))
    channels = tuple(sorted(k for k, r in rows.items() if r.category == "communications" and "message_read" in r.read_capabilities))
    return {"crm": crm, "channels": channels}


def summarize_provider_truth(rows: Iterable[ProviderTruthRow] | None = None) -> dict[str, Any]:
    selected = tuple(rows or build_provider_truth_matrix())
    return {
        "total": len(selected), "live_ready": sum(row.live_ready for row in selected),
        "read_only_supported": sum(row.read_only_supported for row in selected),
        "write_supported": sum(row.write_supported for row in selected),
        "approval_required": sum(row.approval_required for row in selected),
        "placeholder_endpoints": sum(row.has_placeholder_endpoint for row in selected),
        "admin_visible": sum(row.admin_visible for row in selected),
        "by_status": {status.value: sum(row.status == status.value for row in selected) for status in ProviderTruthStatus},
        "by_risk_level": {level: sum(row.risk_level == level for row in selected) for level in ("low", "medium", "high")},
        "live_ready_policy": "guarded_write: only explicitly allowlisted providers with approval/evidence guard may be live-write-ready",
    }


__all__ = [
    "CANON_PROVIDER_TRUTH_MATRIX", "ProviderTruthRow", "ProviderTruthStatus", "build_provider_truth_matrix",
    "LIVE_EVIDENCE_CHECKS", "SALES_CRM_READS", "live_evidence_payload", "provider_channel_live_readiness", "sales_source_provider_keys",
    "provider_truth_map", "provider_runtime_truth_map", "provider_runtime_metrics_truth_map", "provider_quota_truth_map", "list_provider_truth_payloads", "summarize_provider_truth",
]
