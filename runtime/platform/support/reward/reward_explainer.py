from __future__ import annotations


class RewardExplainer:
    def explain(self, components: dict[str, float]) -> str:
        parts = [f"{name}={value:.4f}" for name, value in sorted(components.items())]
        return ", ".join(parts)

__all__ = [
    "RewardExplainer",
]
