from __future__ import annotations
CANON_HEADLESS_RUNTIME_PROVIDER_FINAL_OWNER = True


from dataclasses import dataclass
from typing import Protocol

from execution.headless_boot import build_headless_runtime


CANON_API_HEADLESS_RUNTIME_PROVIDER = True
CANON_API_HEADLESS_RUNTIME_PROVIDER_SINGLE_OWNER = True
CANON_API_HEADLESS_RUNTIME_PROVIDER_NO_DECISION_LOGIC = True


class HeadlessRuntimeLike(Protocol):
    contract: object
    business_memory_query: object


@dataclass(slots=True)
class HeadlessRuntimeProvider:
    """Canonical API-side owner for headless runtime acquisition."""

    runtime: HeadlessRuntimeLike | None = None

    def get_runtime(self) -> HeadlessRuntimeLike:
        runtime = self.runtime
        if runtime is None:
            runtime = build_headless_runtime()
            self.runtime = runtime
        return runtime

    def contract_runtime(self) -> object:
        return self.get_runtime().contract

    def business_memory_query(self) -> object:
        return self.get_runtime().business_memory_query



def build_headless_runtime_provider(*, runtime: HeadlessRuntimeLike | None = None) -> HeadlessRuntimeProvider:
    return HeadlessRuntimeProvider(runtime=runtime)



def build_default_headless_runtime_provider() -> HeadlessRuntimeProvider:
    return build_headless_runtime_provider()


__all__ = [
    'CANON_API_HEADLESS_RUNTIME_PROVIDER',
    'CANON_API_HEADLESS_RUNTIME_PROVIDER_SINGLE_OWNER',
    'CANON_API_HEADLESS_RUNTIME_PROVIDER_NO_DECISION_LOGIC',
    'HeadlessRuntimeLike',
    'HeadlessRuntimeProvider',
    'build_headless_runtime_provider',
    'build_default_headless_runtime_provider',
]
