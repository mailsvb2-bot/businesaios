from __future__ import annotations


class SignificanceExplainer:
    def explain(self, *, p_value: float, significant: bool) -> str:
        if significant:
            return f"p-value={p_value:.4f}; result is statistically significant at alpha=0.05"
        return f"p-value={p_value:.4f}; result is not statistically significant at alpha=0.05"
