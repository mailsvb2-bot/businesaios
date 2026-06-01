from __future__ import annotations

from execution.inference_provider_contract import InferenceProvider

CANON_RUNTIME_INFERENCE_PROVIDER_REGISTRY = True


class InferenceProviderRegistry:
    def __init__(self, providers: list[InferenceProvider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    def as_dict(self) -> dict[str, InferenceProvider]:
        return dict(self._providers)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
