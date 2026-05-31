from __future__ import annotations

from dataclasses import asdict

from core.world_model.types import BusinessState, CompletenessReport


class StateCompletenessEvaluator:
    REQUIRED_FIELDS = (
        "customer.customer_id",
        "product.product_id",
        "market.channel",
        "market.geo",
    )

    def evaluate(self, *, business_state: BusinessState) -> CompletenessReport:
        flat = self._flatten(asdict(business_state))
        missing = []
        present = []
        for field in self.REQUIRED_FIELDS:
            value = flat.get(field)
            if self._is_missing(value):
                missing.append(field)
            else:
                present.append(field)
        score = len(present) / float(len(self.REQUIRED_FIELDS) or 1)
        return CompletenessReport(score=float(score), missing_fields=tuple(missing), present_fields=tuple(present))

    def _flatten(self, payload: dict, *, prefix: str = "") -> dict[str, object]:
        out: dict[str, object] = {}
        for key, value in payload.items():
            full = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                out.update(self._flatten(value, prefix=full))
            else:
                out[full] = value
        return out

    def _is_missing(self, value: object) -> bool:
        if value is None:
            return True
        return isinstance(value, str) and value.strip().lower() in {"", "unknown"}
