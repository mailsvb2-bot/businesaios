from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PolicyDenials:
    counts: dict[str, int] = field(default_factory=dict)
    guardrails_violation: bool = False

    def add(self, operator_key: str, safe_mode: bool) -> None:
        self.counts[operator_key] = self.counts.get(operator_key, 0) + 1
        if safe_mode:
            self.guardrails_violation = True

    def total(self) -> int:
        return sum(self.counts.values())
