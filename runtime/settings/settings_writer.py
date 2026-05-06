from __future__ import annotations

from typing import Protocol


class SettingsWriter(Protocol):

    def set(self, *, tenant_id: str, key: str, value: dict) -> None:
        ...
