from __future__ import annotations

from typing import Any, Protocol


class SettingsGateway(Protocol):
    def get_value(self, *, tenant_id: str, key: str) -> Any:
        ...

    def set_value(self, *, tenant_id: str, key: str, value: list[dict]) -> None:
        ...
