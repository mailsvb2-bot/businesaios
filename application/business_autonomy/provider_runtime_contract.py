from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_PROVIDER_RUNTIME_CONTRACT = True


@dataclass(frozen=True)
class ProviderHealthProbeResult:
    provider_key: str
    status: str
    probe_mode: str
    reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderWebhookContract:
    provider_key: str
    verification_kind: str
    header_names: tuple[str, ...]
    enabled: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)




@dataclass(frozen=True)
class ProviderWebhookReplayDecision:
    provider_key: str
    event_key: str
    resolution: str
    accepted: bool
    owner_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderSyncRunResult:
    provider_key: str
    operation: str
    mode: str
    status: str
    accepted: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderWebhookIngressResult:
    provider_key: str
    event_key: str
    accepted: bool
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderSecretLifecycleResult:
    provider_key: str
    action: str
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)




@dataclass(frozen=True)
class ProviderSecretCompromiseResult:
    provider_key: str
    action: str
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderScheduledSyncResult:
    provider_key: str
    operation: str
    scheduled: bool
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)



@dataclass(frozen=True)
class ProviderLiveProbeResult:
    provider_key: str
    mode: str
    status: str
    ok: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderPaginationRunResult:
    provider_key: str
    operation: str
    mode: str
    status: str
    accepted: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderOperationPlan:
    provider_key: str
    operations: tuple[str, ...]
    read_operations: tuple[str, ...]
    write_operations: tuple[str, ...]
    webhook_enabled: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


__all__ = [
    'CANON_PROVIDER_RUNTIME_CONTRACT',
    'ProviderHealthProbeResult',
    'ProviderWebhookContract',
    'ProviderWebhookReplayDecision',
    'ProviderSyncRunResult',
    'ProviderWebhookIngressResult',
    'ProviderSecretLifecycleResult',
    'ProviderSecretCompromiseResult',
    'ProviderScheduledSyncResult',
    'ProviderLiveProbeResult',
    'ProviderPaginationRunResult',
    'ProviderOperationPlan',
]
