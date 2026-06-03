from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from collections.abc import Iterable, Mapping

from application.business_autonomy.integration_capability_catalog import CapabilityStatus, list_integration_capabilities
from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_catalog import PROVIDERS
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
_GUARDED_WRITE_SUPPORTED: frozenset[str] = frozenset()


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
    base_url = str(binding.get("base_url") or "").strip().lower()
    return bool(base_url) and not _has_placeholder_endpoint(binding) and base_url.startswith(("https://", "postgres://", "redis://"))


def _capability_status_by_provider() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for capability in list_integration_capabilities(include_roadmap=True):
        for provider_key in capability.provider_keys:
            result.setdefault(provider_key, []).append(capability.status.value)
    return result


def _best_capability_status(provider_key: str, status_map: Mapping[str, list[str]]) -> str:
    return max(status_map.get(provider_key) or [CapabilityStatus.NOT_IMPLEMENTED.value], key=lambda value: _STATUS_RANK.get(value, 0))


def _risk_level(provider: ProviderDefinition, write_capabilities: Iterable[str]) -> str:
    if provider.domain in _HIGH_RISK_DOMAINS or provider.provider_key in _HIGH_RISK_PROVIDERS:
        return "high"
    return "medium" if tuple(write_capabilities) else "low"


def _truth_status(*, capability_status: str, has_real_endpoint: bool, has_placeholder_endpoint: bool, read_only_supported: bool, write_supported: bool) -> str:
    if capability_status in {CapabilityStatus.NOT_IMPLEMENTED.value, CapabilityStatus.NOT_FOUND.value}:
        return ProviderTruthStatus.NOT_IMPLEMENTED.value
    if capability_status == CapabilityStatus.CONTRACT_ONLY.value:
        return ProviderTruthStatus.CONTRACT_ONLY.value
    if has_real_endpoint and not has_placeholder_endpoint and read_only_supported:
        return ProviderTruthStatus.LIVE_READY.value if write_supported else ProviderTruthStatus.READ_ONLY_READY.value
    return ProviderTruthStatus.IMPLEMENTED.value if capability_status == CapabilityStatus.IMPLEMENTED.value else ProviderTruthStatus.PARTIAL.value


def _truth_row(provider: ProviderDefinition, *, planner: ProviderSyncRuntimePlanner, bindings: ProviderTransportBindings, capability_statuses: Mapping[str, list[str]]) -> ProviderTruthRow:
    binding = bindings.describe(provider)
    plan = planner.describe(provider)
    read_capabilities, write_capabilities = tuple(plan.read_operations), tuple(plan.write_operations)
    required_credentials = _required_credentials(provider)
    has_placeholder_endpoint, has_real_endpoint = _has_placeholder_endpoint(binding), _has_real_endpoint(binding)
    capability_status = _best_capability_status(provider.provider_key, capability_statuses)
    read_only_supported = bool(read_capabilities) and capability_status not in {CapabilityStatus.NOT_IMPLEMENTED.value, CapabilityStatus.NOT_FOUND.value}
    write_supported = provider.provider_key in _GUARDED_WRITE_SUPPORTED
    status = _truth_status(
        capability_status=capability_status, has_real_endpoint=has_real_endpoint,
        has_placeholder_endpoint=has_placeholder_endpoint, read_only_supported=read_only_supported, write_supported=write_supported,
    )
    live_ready = status == ProviderTruthStatus.LIVE_READY.value and bool(binding.get("live_ready")) and has_real_endpoint and not has_placeholder_endpoint and write_supported
    return ProviderTruthRow(
        provider_key=provider.provider_key, category=provider.domain, display_name=provider.title,
        auth_scheme=str(binding.get("auth_scheme") or "provider_secret_bundle"), required_credentials=required_credentials,
        read_capabilities=read_capabilities, write_capabilities=write_capabilities, status=status, live_ready=live_ready,
        read_only_supported=read_only_supported, write_supported=write_supported,
        approval_required=bool(write_capabilities) or provider.domain in _HIGH_RISK_DOMAINS,
        has_real_endpoint=has_real_endpoint, has_placeholder_endpoint=has_placeholder_endpoint,
        endpoint_source="runtime.business_autonomy.provider_transport_bindings", health_requirements=required_credentials,
        admin_visible=True, owner=_PROVIDER_OWNERS.get(provider.provider_key, "application.business_autonomy.provider_catalog"),
        risk_level=_risk_level(provider, write_capabilities),
        evidence=(f"capability_status={capability_status}", f"transport_binding_live_ready={bool(binding.get('live_ready'))}", "write_supported_requires_guarded_contract"),
    )


def build_provider_truth_matrix(*, providers: Iterable[ProviderDefinition] = PROVIDERS) -> tuple[ProviderTruthRow, ...]:
    planner, bindings, statuses = ProviderSyncRuntimePlanner(), ProviderTransportBindings(), _capability_status_by_provider()
    return tuple(sorted((_truth_row(provider, planner=planner, bindings=bindings, capability_statuses=statuses) for provider in providers), key=lambda row: (row.category, row.provider_key)))


def provider_truth_map() -> dict[str, ProviderTruthRow]:
    return {row.provider_key: row for row in build_provider_truth_matrix()}


def list_provider_truth_payloads() -> list[dict[str, Any]]:
    return [row.to_payload() for row in build_provider_truth_matrix()]


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
        "live_ready_policy": "read_only_advisory: external writes are not live-ready until approval/evidence guard is explicitly wired",
    }


__all__ = [
    "CANON_PROVIDER_TRUTH_MATRIX", "ProviderTruthRow", "ProviderTruthStatus", "build_provider_truth_matrix",
    "provider_truth_map", "list_provider_truth_payloads", "summarize_provider_truth",
]
