from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from security.kms_provider_contract import KMSProvider, KMSProviderCapability


CANON_KMS_PROVIDER_BACKEND = True


@dataclass(frozen=True)
class KMSProviderSelectionRequest:
    operation_kind: str
    require_hsm_backed_keys: bool = False
    require_encryption: bool = True
    require_signing: bool = False
    preferred_provider_name: str | None = None

    def validate(self) -> None:
        if not str(self.operation_kind or '').strip():
            raise ValueError('operation_kind is required')
        preferred = None if self.preferred_provider_name is None else str(self.preferred_provider_name).strip()
        if self.preferred_provider_name is not None and not preferred:
            raise ValueError('preferred_provider_name must be non-empty when provided')


@dataclass(frozen=True)
class KMSProviderSelection:
    provider_name: str
    capability: KMSProviderCapability
    reason: str


class KMSProviderBackendSelector:
    """Canonical selector for capability-aware KMS/HSM provider routing.

    Keeps provider choice in one owner-layer instead of spreading ad-hoc selection
    logic across security and runtime surfaces.
    """

    def resolve_provider(self, *, providers: Iterable[KMSProvider], request: KMSProviderSelectionRequest) -> KMSProviderSelection:
        request.validate()
        candidates: list[tuple[KMSProviderCapability, int]] = []
        for provider in providers:
            capability = provider.capability()
            if request.require_hsm_backed_keys and not capability.supports_hsm_backed_keys:
                continue
            if request.require_encryption and not capability.supports_encryption:
                continue
            if request.require_signing and not capability.supports_signing:
                continue
            score = 0
            if capability.supports_hsm_backed_keys:
                score += 100
            if capability.supports_rotation:
                score += 10
            if request.preferred_provider_name and capability.provider_name == request.preferred_provider_name:
                score += 1000
            candidates.append((capability, score))
        if not candidates:
            raise KeyError(
                'no kms provider satisfies selection request: '
                f'operation_kind={request.operation_kind} require_hsm_backed_keys={request.require_hsm_backed_keys}'
            )
        candidates.sort(key=lambda item: (item[1], item[0].provider_name), reverse=True)
        capability, _score = candidates[0]
        if request.preferred_provider_name and capability.provider_name == request.preferred_provider_name:
            reason = 'preferred provider satisfied capability requirements'
        elif request.require_hsm_backed_keys and capability.supports_hsm_backed_keys:
            reason = 'selected strongest hsm-backed provider'
        else:
            reason = 'selected strongest available provider'
        return KMSProviderSelection(provider_name=capability.provider_name, capability=capability, reason=reason)


__all__ = [
    'CANON_KMS_PROVIDER_BACKEND',
    'KMSProviderBackendSelector',
    'KMSProviderSelection',
    'KMSProviderSelectionRequest',
]


KMSProviderBackendSelector.select = KMSProviderBackendSelector.resolve_provider
