from __future__ import annotations

from typing import Any


class AdapterBase:
    def __init__(self, *, runner: Any) -> None:
        self._runner = runner

    def send(self, msg: Any) -> Any:
        return self._runner.send(msg)
