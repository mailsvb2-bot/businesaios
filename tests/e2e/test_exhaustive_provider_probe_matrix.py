from __future__ import annotations

from collections import Counter
from typing import Any

from application.business_autonomy.provider_catalog import PROVIDERS
from runtime.business_autonomy.provider_connector_health import (
    _REQUIRED_BY_PROVIDER,
    ProviderConnectorHealthService,
)
from runtime.business_autonomy.provider_http_live_clients import (
    build_live_http_transports,
)
from runtime.business_autonomy.provider_live_probe_runtime import (
    ProviderLiveProbeRuntime,
)
from runtime.business_autonomy.provider_transport_bindings import (
    provider_transport_binding_for_key,
)
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


class _MemoryIncidentRegistry:
    def append(self, row: dict[str, Any]) -> dict[str, Any]:
        return dict(row)


def _secret_value(field_key: str) -> str:
    values = {
        "dsn": "postgresql://user:pass@localhost:5432/app",
        "redis_url": "redis://default:pass@localhost:6379/0",
        "endpoint": "https://clickhouse.example.test",
        "store_url": "https://shop.example.test",
        "from_address": "ops@example.test",
        "bot_token": "123456:synthetic-token",
        "phone_number_id": "1234567890",
        "customer_id": "1234567890",
    }
    return values.get(field_key, f"synthetic-{field_key}")


def _seed_required_secrets(vault: InMemorySecretVault, provider: Any, *, live: bool = False) -> None:
    live_required = set(provider_transport_binding_for_key(provider.provider_key).get("live_required_secrets", ())) if live else set()
    for field in provider.secret_fields:
        if not field.required and field.field_key not in live_required:
            continue
        ref = SecretRef(
            tenant_id="tenant-probe-matrix",
            connector_id=provider.connector_id,
            scope="business-probe-matrix",
            secret_name=f"{provider.connector_id}.{field.field_key}",
        )
        vault.put(
            SecretRecord(
                ref=ref,
                ciphertext=b"pending",
                source=SecretSource.CONNECTOR,
            ),
            plaintext=_secret_value(field.field_key).encode(),
        )


def test_provider_health_requirements_cannot_drift_from_catalog() -> None:
    cases = 0
    for provider in PROVIDERS:
        catalog_required = {
            field.field_key for field in provider.secret_fields if field.required
        }
        health_required = set(
            _REQUIRED_BY_PROVIDER.get(provider.provider_key, catalog_required)
        )
        assert health_required <= catalog_required, provider.provider_key
        cases += 1
    assert cases == len(PROVIDERS)


def test_every_provider_reaches_declared_dry_run_state_without_network(
    monkeypatch,
    tmp_path,
) -> None:
    network_attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def _network_forbidden(*args: Any, **kwargs: Any) -> None:
        network_attempts.append((args, kwargs))
        raise AssertionError("provider dry-run attempted network access")

    monkeypatch.setattr(
        "runtime.business_autonomy.provider_http_live_clients._sync_request",
        _network_forbidden,
    )
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    transport_keys = set(build_live_http_transports(InMemorySecretVault(), bind_live_network=False))
    statuses: Counter[str] = Counter()
    cases = 0
    for provider in PROVIDERS:
        vault = InMemorySecretVault()
        _seed_required_secrets(vault, provider)
        health = ProviderConnectorHealthService(vault).probe(
            provider=provider,
            tenant_id="tenant-probe-matrix",
            business_id="business-probe-matrix",
            probe_mode="dry_run",
        )
        assert health.status == "ready_for_credentials", provider.provider_key

        runtime = ProviderLiveProbeRuntime(
            secret_vault=vault,
            transports=build_live_http_transports(vault, bind_live_network=False),
            incident_registry=_MemoryIncidentRegistry(),
        )
        result = runtime.run(
            provider=provider,
            tenant_id="tenant-probe-matrix",
            business_id="business-probe-matrix",
            mode="dry_run",
        )
        expected = (
            "probe_prepared_only"
            if provider.provider_key in transport_keys
            else "probe_unsupported"
        )
        assert result.status == expected, provider.provider_key
        assert result.ok is (expected == "probe_prepared_only")
        statuses[result.status] += 1
        cases += 1

    assert cases == len(PROVIDERS)
    assert statuses == {
        "probe_prepared_only": len(transport_keys),
        "probe_unsupported": len(PROVIDERS) - len(transport_keys),
    }
    assert network_attempts == []
    assert not (tmp_path / "data").exists()


def test_every_provider_live_probe_readiness_matches_transport_binding() -> None:
    cases = 0
    for provider in PROVIDERS:
        vault = InMemorySecretVault()
        _seed_required_secrets(vault, provider, live=True)
        health = ProviderConnectorHealthService(vault).probe(
            provider=provider,
            tenant_id="tenant-probe-matrix",
            business_id="business-probe-matrix",
            probe_mode="live",
        )
        binding = provider_transport_binding_for_key(provider.provider_key)
        live_probe_ready = bool(binding.get("live_probe_ready", binding.get("live_ready")))
        expected = "ready_for_live_probe" if live_probe_ready else "live_probe_unsupported"
        assert health.status == expected, provider.provider_key
        assert bool(health.metadata.get("live_probe_supported")) is live_probe_ready
        cases += 1
    assert cases == len(PROVIDERS)
