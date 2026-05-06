from __future__ import annotations

from dataclasses import dataclass

from ..types import CustomerValueSignal


@dataclass
class StaticCustomerValueReader:
    signal: CustomerValueSignal

    def read(self) -> CustomerValueSignal:
        return self.signal
