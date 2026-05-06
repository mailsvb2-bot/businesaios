from __future__ import annotations

import signal
from dataclasses import dataclass
from types import FrameType
from typing import Callable


@dataclass(frozen=True)
class SignalHandlerInstaller:
    on_shutdown_signal: Callable[[], None]

    def install(self) -> None:
        def _handler(signum: int, frame: FrameType | None) -> None:
            _ = (signum, frame)
            self.on_shutdown_signal()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
