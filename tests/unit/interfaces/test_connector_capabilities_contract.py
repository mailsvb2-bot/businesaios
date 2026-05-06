from __future__ import annotations

from interfaces.common.base_connector import BaseConnector


def test_base_connector_exposes_capability_surface() -> None:
    connector = BaseConnector()
    capabilities = connector.capabilities()
    assert capabilities["read"] is True
    assert capabilities["write"] is False
    assert connector.supports_verify() is False
    assert connector.supports_idempotency() is False


def test_base_connector_rejects_unsupported_idempotency_and_dry_run() -> None:
    connector = BaseConnector()
    dry_run_result = connector.execute("publish", {}, dry_run=True)
    assert dry_run_result.code == "dry_run_not_supported"
    idem_result = connector.execute("publish", {}, idempotency_key="idem-1")
    assert idem_result.code == "idempotency_not_supported"
