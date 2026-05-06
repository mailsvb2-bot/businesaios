from __future__ import annotations

from interfaces.common.base_connector import BaseConnector
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_maturity import ConnectorMaturity


class CallTrackingConnector(BaseConnector):
    connector_name = "call_tracking_connector"

    def connector_maturity(self) -> ConnectorMaturity:
        return ConnectorMaturity.PLACEHOLDER

    def connector_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            read=False,
            write=False,
            verify=False,
            dry_run=True,
            idempotent=False,
            metadata={"maturity": self.connector_maturity().value},
        )
