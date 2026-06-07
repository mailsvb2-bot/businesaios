from __future__ import annotations

from typing import Any
from collections.abc import Callable


class RunnerBase:
    def __init__(
        self,
        *,
        build_config: Callable[[], Any],
        send_raw: Callable[..., Any],
        map_result: Callable[..., Any],
    ) -> None:
        self._cfg = build_config()
        self._send_raw = send_raw
        self._map_result = map_result

    def send(self, msg: Any) -> Any:
        raw = self._send_raw(cfg=self._cfg, msg=msg)
        return self._map_result(msg=msg, raw=raw)
