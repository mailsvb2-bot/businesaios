from __future__ import annotations

from typing import Any, Protocol


class SettingsReader(Protocol):

    def get(self, *, tenant_id: str, key: str) -> Any:
        ...
