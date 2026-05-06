from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any


class InMemorySettingsGateway:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Any] = {}
        self._lock = RLock()

    def get_value(self, *, tenant_id: str, key: str) -> Any:
        with self._lock:
            value = self._items.get((str(tenant_id), str(key)))
            return deepcopy(value)

    def set_value(self, *, tenant_id: str, key: str, value: Any) -> None:
        with self._lock:
            self._items[(str(tenant_id), str(key))] = deepcopy(value)
