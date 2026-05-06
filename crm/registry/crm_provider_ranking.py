from __future__ import annotations

from crm.crm_provider_contract import CrmProvider


class CrmProviderRanking:
    def score(self, provider: CrmProvider, *, required_capabilities: tuple[str, ...]) -> int:
        descriptor = provider.capability_descriptor
        score = provider.default_rank
        for capability_name in required_capabilities:
            if descriptor.supports(capability_name):
                score += 20
            else:
                score -= 1000
        if descriptor.can_verify_writes:
            score += 15
        if descriptor.supports_idempotency:
            score += 10
        if descriptor.maturity == 'real':
            score += 25
        return score
