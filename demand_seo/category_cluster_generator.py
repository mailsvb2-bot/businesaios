from __future__ import annotations

class CategoryClusterGenerator:
    def build(self, categories: tuple[str, ...]) -> tuple[dict[str, object], ...]:
        return tuple({"category": c} for c in categories)
