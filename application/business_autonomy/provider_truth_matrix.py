from __future__ import annotations

"""Canonical provider truth matrix.

This module is the single read model for provider readiness claims.  It does
not execute provider traffic and it intentionally downgrades optimistic
registry/transport/runtime claims into conservative admin-visible truth.

Rules enforced here:
- provider-in-catalog is not implementation proof;
- transport endpoint is not live readiness proof;
- placeholder/example endpoints are never live-ready;
- write operations are capability declarations, not write-supported status;
- external write/spend remains blocked until explicit approval/evidence guard
  ownership is represented in this matrix.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

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
    "example.invalid",
    ".example",
    "example.com",
    "{",
    "}",
    "configured-per-business",
    "vendor-configured",
    "smtp+https://provider",
    "https://sms-gateway.example",
    "https://clickhouse",
)

_PROVIDER_OWNERS: Mapping[str, str] = {
    "telegram_bot": "interfaces.messaging.telegram",
    "whatsapp_cloud": "interfaces.messaging.whatsapp",
    "email_connector": "interfaces.communications.email",
    "sms_connector": "interfaces.communications.sms",
    "call_tracking": "interfaces.communications.call_tracking",
    "generic_website": "interfaces.platforms.website",
    "webflow": "interfaces.platforms.webflow",
    "wordpress": "interfaces.platforms.wordpress",
    "shopify": "interfaces.platforms.shopify",
    "woocommerce": "interfaces.platforms.woocommerce",
    "amazon_marketplace": "interfaces.marketplaces.amazon",
    "ebay_marketplace": "interfaces.marketplaces.ebay",
    "etsy_marketplace": "interfaces.marketplaces.etsy",
    "wildberries_marketplace": "interfaces.marketplaces.wildberries",
    "ozon_marketplace": "interfaces.marketplaces.ozon",
    "hubspot": "interfaces.crm.hubspot",
    "meta_ads": "interfaces.ads.meta",
    "google_ads": "interfaces.ads.google",
    "tiktok_ads": "interfaces.ads.tiktok",
    "postgres_runtime": "infrastructure.postgres",
    "redis_runtime": "infrastructure.redis",
    "clickhouse_export": "infrastructure.clickhouse",
}

_HIGH_RISK_DOMAINS = {"ads", "marketplace", "platform_infra"}
_HIGH_RISK_PROVIDERS = {"sms_connector", "whatsapp_cloud"}

# Explicitly guarded write support is intentionally empty for external providers
# in the read-only/advisory pilot.  Runtime operation declarations are preserved
# as write_capabilities, but write_supported remains false until the approval /
# budget/risk/evidence contract is wired and audited per provider.
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
        return {
            "provider_key": self.provider_key,
            "category": self.category,
            "display_name": self.display_name,
            "auth_scheme": self.auth_scheme,
            "required_credentials": list(self.required_credentials),
            "read_capabilities": list(self.read_capabilities),
            "write_capabilities": list(self.write_capabilities),
            "status": self.status,
            "live_ready": self.live_ready,
            "read_only_supported": self.read_only_supported,
            "write_supported": self.write_supported,
            "approval_required": self.approval_required,
            "has_real_endpoint": self.has_real_endpoint,
            "has_placeholder_endpoint": self.has_placeholder_endpoint,
            "endpoint_source": self.endpoint_source,
            "health_requirements": list(self.health_requirements),
            "admin_visible": self.admin_visible,
            "owner": self.owner,
            "risk_level": self.risk_level,
            "evidence": list(self.evidence),
            "live_ready_false_reason": None if self.live_ready else self._live_ready_false_reason(),
        }

    def _live_ready_false_reason(self) -> str:
        if self.has_placeholder_endpoint:
            return "placeholder_endpoint"
        if self.status in {ProviderTruthStatus.NOT_IMPLEMENTED.value, ProviderTruthStatus.CONTRACT_ONLY.value}:
            return self.status
        if not self.read_only_supported:
            return "no_read_capability"
        return "live_readiness_not_proven"


def _required_credentials(provider: ProviderDefinition) -> tuple[str, ...]:
    return tuple(field.secret_name for field in provider.secret_fields if field.required)


def _has_placeholder_endpoint(binding: Mapping[str, Any]) -> bool:
    text = " ".join(str(binding.get(name) or "") for name in ("base_url", "probe_path", "sync_path_family"))
    lowered = text.lower()
    return any(token in lowered for token in _PLACEHOLDER_TOKENS)


def _has_real_endpoint(binding: Mapping[str, Any]) -> bool:
    base_url = str(binding.get("base_url") or "").strip().lower()
    if not base_url or _has_placeholder_endpoint(binding):
        return False
    return base_url.startswith(("https://", "postgres://", "redis://"))


def _capability_status_by_provider() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for capability in list_integration_capabilities(include_roadmap=True):
        for provider_key in capability.provider_keys:
            result.setdefault(provider_key, []).append(capability.status.value)
    return result


def _best_capability_status(provider_key: str, status_map: Mapping[str, list[str]]) -> str:
    statuses = status_map.get(provider_key) or []
    if not statuses:
        return CapabilityStatus.NOT_IMPLEMENTED.value
    return max(statuses, key=lambda value: _STATUS_RANK.get(value, 0))


def _risk_level(provider: ProviderDefinition, write_capabilities: Iterable[str]) -> str:
    if provider.domain in _HIGH_RISK_DOMAINS or provider.provider_key in _HIGH_RISK_PROVIDERS:
        return "high"
    if tuple(write_capabilities):
        return "medium"
    return "low"


def _truth_status(*, capability_status: str, has_real_endpoint: bool, has_placeholder_endpoint: bool, read_only_supported: bool, write_supported: bool) -> str:
    if capability_status in {CapabilityStatus.NOT_IMPLEMENTED.value, CapabilityStatus.NOT_FOUND.value}:
        return ProviderTruthStatus.NOT_IMPLEMENTED.value
    if capability_status == CapabilityStatus.CONTRACT_ONLY.value:
        return ProviderTruthStatus.CONTRACT_ONLY.value
    if has_real_endpoint and not has_placeholder_endpoint and read_only_supported:
        if write_supported:
            return ProviderTruthStatus.LIVE_READY.value
        return ProviderTruthStatus.READ_ONLY_READY.value
    if capability_status == CapabilityStatus.IMPLEMENTED.value:
        return ProviderTruthStatus.IMPLEMENTED.value
    return ProviderTruthStatus.PARTIAL.value


def build_provider_truth_matrix(*, providers: Iterable[ProviderDefinition] = PROVIDERS) -> tuple[ProviderTruthRow, ...]:
    planner = ProviderSyncRuntimePlanner()
    bindings = ProviderTransportBindings()
    capability_statuses = _capability_status_by_provider()
    rows: list[ProviderTruthRow] = []
    for provider in providers:
        binding = bindings.describe(provider)
        plan = planner.describe(provider)
        read_capabilities = tuple(plan.read_operations)
        write_capabilities = tuple(plan.write_operations)
        required_credentials = _required_credentials(provider)
        has_placeholder_endpoint = _has_placeholder_endpoint(binding)
        has_real_endpoint = _has_real_endpoint(binding)
        capability_status = _best_capability_status(provider.provider_key, capability_statuses)
        read_only_supported = bool(read_capabilities) and capability_status not in {CapabilityStatus.NOT_IMPLEMENTED.value, CapabilityStatus.NOT_FOUND.value}
        write_supported = provider.provider_key in _GUARDED_WRITE_SUPPORTED
        approval_required = bool(write_capabilities) or provider.domain in _HIGH_RISK_DOMAINS
        status = _truth_status(
            capability_status=capability_status,
            has_real_endpoint=has_real_endpoint,
            has_placeholder_endpoint=has_placeholder_endpoint,
            read_only_supported=read_only_supported,
            write_supported=write_supported,
        )
        live_ready = (
            status == ProviderTruthStatus.LIVE_READY.value
            and bool(binding.get("live_ready"))
            and has_real_endpoint
            and not has_placeholder_endpoint
            and write_supported
        )
        evidence = (
            f"capability_status={capability_status}",
            f"transport_binding_live_ready={bool(binding.get('live_ready'))}",
            "write_supported_requires_guarded_contract",
        )
        rows.append(
            ProviderTruthRow(
                provider_key=provider.provider_key,
                category=provider.domain,
                display_name=provider.title,
                auth_scheme=str(binding.get("auth_scheme") or "provider_secret_bundle"),
                required_credentials=required_credentials,
                read_capabilities=read_capabilities,
                write_capabilities=write_capabilities,
                status=status,
                live_ready=live_ready,
                read_only_supported=read_only_supported,
                write_supported=write_supported,
                approval_required=approval_required,
                has_real_endpoint=has_real_endpoint,
                has_placeholder_endpoint=has_placeholder_endpoint,
                endpoint_source="runtime.business_autonomy.provider_transport_bindings",
                health_requirements=required_credentials,
                admin_visible=True,
                owner=_PROVIDER_OWNERS.get(provider.provider_key, "application.business_autonomy.provider_catalog"),
                risk_level=_risk_level(provider, write_capabilities),
                evidence=evidence,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.category, row.provider_key)))


def provider_truth_map() -> dict[str, ProviderTruthRow]:
    return {row.provider_key: row for row in build_provider_truth_matrix()}


def list_provider_truth_payloads() -> list[dict[str, Any]]:
    return [row.to_payload() for row in build_provider_truth_matrix()]


def summarize_provider_truth(rows: Iterable[ProviderTruthRow] | None = None) -> dict[str, Any]:
    selected = tuple(rows or build_provider_truth_matrix())
    return {
        "total": len(selected),
        "live_ready": sum(1 for row in selected if row.live_ready),
        "read_only_supported": sum(1 for row in selected if row.read_only_supported),
        "write_supported": sum(1 for row in selected if row.write_supported),
        "approval_required": sum(1 for row in selected if row.approval_required),
        "placeholder_endpoints": sum(1 for row in selected if row.has_placeholder_endpoint),
        "admin_visible": sum(1 for row in selected if row.admin_visible),
        "by_status": {status.value: sum(1 for row in selected if row.status == status.value) for status in ProviderTruthStatus},
        "by_risk_level": {level: sum(1 for row in selected if row.risk_level == level) for level in ("low", "medium", "high")},
        "live_ready_policy": "read_only_advisory: external writes are not live-ready until approval/evidence guard is explicitly wired",
    }


__all__ = [
    "CANON_PROVIDER_TRUTH_MATRIX",
    "ProviderTruthRow",
    "ProviderTruthStatus",
    "build_provider_truth_matrix",
    "provider_truth_map",
    "list_provider_truth_payloads",
    "summarize_provider_truth",
]
