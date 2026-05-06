from __future__ import annotations

from crm.crm_provider_contract import CrmProvider
from crm.registry.crm_provider_ranking import CrmProviderRanking
from crm.registry.crm_provider_registry import CrmProviderRegistry


class CrmProviderSelector:
    def __init__(
        self,
        registry: CrmProviderRegistry,
        ranking: CrmProviderRanking | None = None,
    ) -> None:
        self._registry = registry
        self._ranking = ranking or CrmProviderRanking()

    def choose_provider(self, *, required_capabilities: tuple[str, ...]) -> CrmProvider:
        candidates: list[tuple[int, CrmProvider]] = []
        for provider in self._registry.list_enabled():
            score = self._ranking.score(
                provider,
                required_capabilities=required_capabilities,
            )
            if score >= 0:
                candidates.append((score, provider))

        if not candidates:
            if required_capabilities:
                raise LookupError(
                    f'No enabled CRM provider satisfies capabilities: {required_capabilities}'
                )
            raise LookupError('No enabled CRM providers')

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    select = choose_provider
