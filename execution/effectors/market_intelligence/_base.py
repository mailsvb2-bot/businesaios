from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.effectors.base import ConnectorEffectorBase
from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class MarketIntelEffectorBase(ConnectorEffectorBase):
    connector: Any
    operation: str
    source_family: str

    def __post_init__(self) -> None:
        if not isinstance(self.connector, MarketIntelConnectorBase):
            raise TypeError('connector must be a MarketIntelConnectorBase')


__all__ = ['MarketIntelEffectorBase']
