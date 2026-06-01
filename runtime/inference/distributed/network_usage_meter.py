from __future__ import annotations

from dataclasses import dataclass

CANON_RUNTIME_DISTRIBUTED_NETWORK_USAGE_METER = True


@dataclass
class DistributedNetworkUsage:
    requests: int = 0
    estimated_cost_usd: float = 0.0


class DistributedInferenceNetworkUsageMeter:
    def __init__(self) -> None:
        self._usage = DistributedNetworkUsage()

    def record(self, *, estimated_cost_usd: float) -> None:
        self._usage.requests += 1
        self._usage.estimated_cost_usd += float(estimated_cost_usd)

    def snapshot(self) -> DistributedNetworkUsage:
        return self._usage
