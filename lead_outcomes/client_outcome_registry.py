from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from registry.base_registry import BaseRegistry

CANON_CLIENT_OUTCOME_REGISTRY = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


class ClientOutcomeRegistry(BaseRegistry):
    def __init__(self) -> None:
        super().__init__(kind='client_outcome')

    def has(self, lead_id: str) -> bool:
        return str(lead_id) in self.snapshot()

    def get(self, lead_id: str) -> dict[str, Any]:
        try:
            row = super().get(str(lead_id))
        except KeyError:
            return {}
        return _safe_dict(row)

    def update(self, lead_id: str, payload: Mapping[str, object]) -> None:
        row = self.get(lead_id)
        row.update(dict(payload))
        self.register(str(lead_id), row)


@dataclass(frozen=True, slots=True)
class ClientOutcomeMutation:
    def set_fields(self, registry: ClientOutcomeRegistry, lead_id: str, **fields: object) -> None:
        registry.update(lead_id, fields)
