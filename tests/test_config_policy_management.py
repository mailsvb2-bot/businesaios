from __future__ import annotations

from pathlib import Path

import pytest

from config import (
    ConfigAuditEvent,
    ConfigFeatureFlagResolver,
    ConfigVersioning,
    EnvironmentMatrix,
    FeatureFlagSnapshot,
    InMemoryPolicyConfigStore,
    InMemoryRuntimeConfigStore,
    InMemoryTenantConfigStore,
    PersistentConfigAuditLog,
    PersistentPolicyConfigStore,
    PersistentRuntimeConfigStore,
    PersistentTenantConfigStore,
    PolicyConfigSnapshot,
    RuntimeConfigSnapshot,
    SecretResolutionRequest,
    SecretsResolutionPolicy,
    TenantConfigSnapshot,
    normalize_environment_name,
)
from security.secret_contract import SecretRef
from tenancy.tenant_feature_flags import TenantFeatureFlags


class _Resolver:
    def get(self, ref: SecretRef) -> bytes:
        return f"resolved:{ref.secret_name}:{ref.version}".encode("utf-8")


def test_runtime_config_store_noop_save_and_revision_increment() -> None:
    store = InMemoryRuntimeConfigStore()
    first = store.save(
        RuntimeConfigSnapshot(profile_name="main", environment="production", runtime_settings={"a": 1}),
        actor="tester",
        reason="create",
    )
    same = store.save(
        RuntimeConfigSnapshot(profile_name="main", environment="prod", runtime_settings={"a": 1}),
        actor="tester",
        reason="noop",
        expected_revision=1,
    )
    changed = store.save(
        RuntimeConfigSnapshot(profile_name="main", environment="prod", runtime_settings={"a": 2}),
        actor="tester",
        reason="change",
        expected_revision=1,
    )

    assert first.version is not None
    assert same is first
    assert changed.version is not None
    assert first.version.revision == 1
    assert changed.version.revision == 2
    assert changed.environment == "prod"


def test_policy_config_store_optimistic_concurrency_guard() -> None:
    store = InMemoryPolicyConfigStore()
    saved = store.save(PolicyConfigSnapshot(policy_name="guardrail", scope="runtime", tenant_id="tenant-a", config={"x": 1}))
    assert saved.version is not None
    with pytest.raises(RuntimeError):
        store.save(
            PolicyConfigSnapshot(policy_name="guardrail", scope="runtime", tenant_id="tenant-a", config={"x": 2}),
            expected_revision=999,
        )


def test_tenant_config_store_tracks_history() -> None:
    store = InMemoryTenantConfigStore()
    store.save(TenantConfigSnapshot(tenant_id="tenant-a", feature_flags={"f1": True}))
    store.save(TenantConfigSnapshot(tenant_id="tenant-a", feature_flags={"f1": False}), expected_revision=1)
    history = store.history("tenant-a")
    assert len(history) == 2
    assert history[-1].feature_flags["f1"] is False


def test_feature_flag_resolver_uses_explicit_precedence() -> None:
    resolver = ConfigFeatureFlagResolver(
        environment_snapshot=FeatureFlagSnapshot(
            scope_name="env",
            environment="production",
            flags={"debug": False, "beta": False},
            variants={"rollout": "env"},
        ),
        config_snapshot=FeatureFlagSnapshot(
            scope_name="config",
            environment="prod",
            flags={"beta": True},
            variants={"rollout": "config"},
        ),
        tenant_snapshots={
            "tenant-a": TenantFeatureFlags(
                tenant_id="tenant-a",
                flags={"beta": False, "tenant_only": True},
                variants={"rollout": "tenant"},
            )
        },
    )

    assert resolver.is_enabled("debug", tenant_id="tenant-a") is False
    assert resolver.is_enabled("beta", tenant_id="tenant-a") is False
    assert resolver.is_enabled("tenant_only", tenant_id="tenant-a") is True
    assert resolver.variant("rollout", tenant_id="tenant-a") == "tenant"


@pytest.mark.parametrize(
    ("raw", "expected"),
    (("production", "prod"), ("preprod", "stage"), ("local", "dev"), ("dev", "dev")),
)
def test_environment_alias_normalization(raw: str, expected: str) -> None:
    assert normalize_environment_name(raw) == expected
    assert EnvironmentMatrix.default().require(raw).normalized_environment == expected


def test_secrets_resolution_policy_resolves_and_redacts_nested_values() -> None:
    policy = SecretsResolutionPolicy(required_secret_keys=("password",), allow_plaintext_keys=("username",))
    resolved = policy.resolve_mapping(
        {
            "username": "demo",
            "password": "secret://crm/password?version=v2",
            "nested": {"api_key": "secret://crm/key"},
        },
        tenant_id="tenant-a",
        resolver=_Resolver(),
        connector_id="crm",
        scope="auth",
    )
    redacted = policy.redact_mapping(resolved)

    assert resolved["password"] == "resolved:crm/password:v2"
    assert resolved["nested"]["api_key"] == "resolved:crm/key:current"
    assert redacted["username"] == "demo"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"


def test_secret_resolution_request_builds_secret_ref() -> None:
    request = SecretResolutionRequest(
        tenant_id="tenant-a",
        config_key="password",
        secret_uri="secret://service/credentials?version=v3",
        connector_id="crm",
        scope="auth",
    )
    ref = request.to_secret_ref()
    assert ref == SecretRef(
        tenant_id="tenant-a",
        connector_id="crm",
        scope="auth",
        secret_name="service/credentials",
        version="v3",
    )


def test_config_versioning_is_stable_for_semantically_same_payload() -> None:
    left = {"a": 1, "b": {"x": True}}
    right = {"b": {"x": True}, "a": 1}
    assert ConfigVersioning.is_semantically_same(left_payload=left, right_payload=right) is True


def test_persistent_audit_log_has_valid_chain(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    log = PersistentConfigAuditLog(audit_path)
    log.append(ConfigAuditEvent(namespace="runtime_config", entity_id="global:prod:main", action="upsert"))
    log.append(ConfigAuditEvent(namespace="runtime_config", entity_id="global:prod:main", action="upsert"))
    log.validate_chain()
    assert len(log.read_events()) == 2


def test_persistent_stores_round_trip(tmp_path: Path) -> None:
    runtime = PersistentRuntimeConfigStore(
        path=tmp_path / "runtime.json",
        audit_log_path=tmp_path / "runtime_audit.jsonl",
    )
    policy = PersistentPolicyConfigStore(
        path=tmp_path / "policy.json",
        audit_log_path=tmp_path / "policy_audit.jsonl",
    )
    tenant = PersistentTenantConfigStore(
        path=tmp_path / "tenant.json",
        audit_log_path=tmp_path / "tenant_audit.jsonl",
    )

    runtime.save(RuntimeConfigSnapshot(profile_name="main", environment="prod", runtime_settings={"workers": 2}))
    policy.save(PolicyConfigSnapshot(policy_name="approve", scope="runtime", config={"required": True}))
    tenant.save(TenantConfigSnapshot(tenant_id="tenant-a", runtime_overrides={"workers": 3}))

    runtime_reloaded = PersistentRuntimeConfigStore(
        path=tmp_path / "runtime.json",
        audit_log_path=tmp_path / "runtime_audit.jsonl",
    )
    policy_reloaded = PersistentPolicyConfigStore(
        path=tmp_path / "policy.json",
        audit_log_path=tmp_path / "policy_audit.jsonl",
    )
    tenant_reloaded = PersistentTenantConfigStore(
        path=tmp_path / "tenant.json",
        audit_log_path=tmp_path / "tenant_audit.jsonl",
    )

    assert runtime_reloaded.require(profile_name="main", environment="prod").runtime_settings["workers"] == 2
    assert policy_reloaded.require(policy_name="approve", scope="runtime").config["required"] is True
    assert tenant_reloaded.require("tenant-a").runtime_overrides["workers"] == 3
