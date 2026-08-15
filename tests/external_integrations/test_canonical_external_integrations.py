from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crm.crm_capability_contract import CrmCapabilityDescriptor
from crm.crm_provider_contract import CrmProvider
from crm.onboarding.crm_connection_flow import CrmConnectionFlow
from crm.onboarding.crm_connection_verifier import CrmConnectionVerifier
from crm.onboarding.crm_oauth_contract import CrmOAuthCallbackPayload, CrmOAuthStartRequest
from crm.onboarding.crm_oauth_state_store import InMemoryCrmOAuthStateStore
from crm.registry.crm_connector_registry import CrmConnectorRegistry
from crm.registry.crm_provider_catalog import build_default_provider_catalog
from integration_observations.contracts import ProviderObservationEnvelope
from market_intelligence.contracts import EvidenceRef


class _Connector:
    def __init__(self, provider_key: str, *, live: bool = False) -> None:
        self.provider = CrmProvider(
            provider_key=provider_key,
            display_name=provider_key,
            capability_descriptor=CrmCapabilityDescriptor(provider_key=provider_key),
        )
        self.live = live
        self.exchange_calls = 0

    def supports_live_api(self) -> bool:
        return self.live

    def exchange_oauth_code(self, **_kwargs) -> None:
        self.exchange_calls += 1

    def verify_connection(self, _connection):
        return {
            "verified": True,
            "provider_key": self.provider.provider_key,
            "reason": "verified",
        }


def _flow() -> CrmConnectionFlow:
    return CrmConnectionFlow(
        state_store=InMemoryCrmOAuthStateStore(),
        verifier=CrmConnectionVerifier(),
    )


def _start(flow: CrmConnectionFlow, provider_key: str = "amocrm") -> None:
    flow.start(
        CrmOAuthStartRequest(
            tenant_id="tenant",
            business_id="business",
            provider_key=provider_key,
            redirect_uri="https://app.example/callback",
            state_token="state-1",
        )
    )


def _callback(provider_key: str = "amocrm") -> CrmOAuthCallbackPayload:
    return CrmOAuthCallbackPayload(
        provider_key=provider_key,
        state_token="state-1",
        authorization_code="code-1",
        metadata={},
    )


def test_default_crm_assembly_preserves_existing_and_adds_external_providers() -> None:
    expected = {"hubspot", "pipedrive", "amocrm", "bitrix24", "salesforce"}
    providers = {provider.provider_key: provider for provider in build_default_provider_catalog()}
    connectors = set(CrmConnectorRegistry.build_default().keys())

    assert expected <= set(providers)
    assert expected <= connectors
    assert connectors == set(providers)
    for provider_key in expected:
        assert providers[provider_key].capability_descriptor.provider_key == provider_key


def test_oauth_callback_provider_mismatch_fails_before_token_exchange() -> None:
    flow = _flow()
    _start(flow, "amocrm")
    connector = _Connector("amocrm", live=True)

    with pytest.raises(ValueError, match="callback provider"):
        flow.complete(
            _callback("bitrix24"),
            connector=connector,
            secret_ref="secret-ref",
        )

    assert connector.exchange_calls == 0


def test_oauth_connector_provider_mismatch_fails_before_token_exchange() -> None:
    flow = _flow()
    _start(flow, "amocrm")
    connector = _Connector("bitrix24", live=True)

    with pytest.raises(ValueError, match="connector provider"):
        flow.complete(
            _callback("amocrm"),
            connector=connector,
            secret_ref="secret-ref",
        )

    assert connector.exchange_calls == 0


def test_completed_oauth_connection_does_not_persist_one_time_state_token() -> None:
    flow = _flow()
    _start(flow)
    result = flow.complete(
        _callback(),
        connector=_Connector("amocrm"),
        secret_ref="secret-ref",
    )
    connection = getattr(result, "connection", None) or result

    assert "oauth_state_token" not in connection.metadata
    assert "state-1" not in repr(dict(connection.metadata))


@pytest.mark.parametrize(
    "key",
    ["executorCommand", "direct-action", "approved.action", "finalDecision"],
)
def test_provider_observation_cannot_cross_decision_execution_boundary(key: str) -> None:
    with pytest.raises(ValueError, match="decision boundary"):
        ProviderObservationEnvelope(
            tenant_id="tenant",
            business_id="business",
            provider_key="external",
            observation_type="provider.snapshot",
            observed_at=datetime.now(timezone.utc),
            payload={"facts": {key: "must-not-cross"}},
        )


def test_provider_observation_checks_metadata_boundary_too() -> None:
    with pytest.raises(ValueError, match="decision boundary"):
        ProviderObservationEnvelope(
            tenant_id="tenant",
            business_id="business",
            provider_key="salesforce",
            observation_type="crm.snapshot",
            observed_at=datetime.now(timezone.utc),
            payload={"deal_count": 2},
            metadata={"trace": {"executor_command": "sync-now"}},
        )


def test_market_evidence_rejects_nested_decision_payload() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="decision boundary"):
        EvidenceRef(
            provider_key="semrush",
            source_kind="keyword",
            source_id="source",
            observed_at=now,
            retrieved_at=now,
            metadata={"provenance": {"candidate": {"final_decision": "raise-price"}}},
        )


def test_market_evidence_accepts_factual_provenance() -> None:
    now = datetime.now(timezone.utc)
    ref = EvidenceRef(
        provider_key="semrush",
        source_kind="keyword",
        source_id="source",
        observed_at=now,
        retrieved_at=now,
        metadata={"database": "us", "api_version": "v3"},
    )

    assert ref.provider_key == "semrush"
