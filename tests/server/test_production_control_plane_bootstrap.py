from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from entrypoints.api.api_key_policy import PersistentApiKeyStore
from governance.rbac_contract import RoleId
from scripts.server import bootstrap_production_control_plane as bootstrap
from tenancy.tenant_contract import TenantRecord, TenantStatus
from tenancy.tenant_registry import PersistentTenantRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_LIFECYCLE = PROJECT_ROOT / "scripts" / "server" / "bootstrap_and_verify_production.sh"
RUNTIME_VERIFIER = PROJECT_ROOT / "scripts" / "server" / "verify_runtime_host_contract.sh"
RUNBOOK = PROJECT_ROOT / "docs" / "operations" / "production-control-plane-bootstrap.md"
PRODUCTION_ENV_TEMPLATE = PROJECT_ROOT / ".env.example.prod"


def _prepare(tmp_path: Path, *, tenant_status: TenantStatus = TenantStatus.ACTIVE) -> tuple[Path, Path, Path]:
    api_store = tmp_path / "runtime" / "api" / "api_keys.json"
    tenant_store = tmp_path / "runtime" / "tenancy" / "tenant_registry.json"
    registry = PersistentTenantRegistry(path=tenant_store)
    registry.register(
        TenantRecord(
            tenant_id="production-smoke",
            display_name="Production smoke",
            status=tenant_status,
        )
    )
    env_file = tmp_path / "api.env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=prod",
                "DATA_DIR=" + str(tmp_path / "runtime"),
                "API_CONTROL_PLANE_API_KEY_PEPPER=test-production-pepper",
                "BUSINESAIOS_API_KEY_STORE_BACKEND=file",
                "BUSINESAIOS_API_KEY_STORE_PATH=" + str(api_store),
                "BUSINESAIOS_TENANT_REGISTRY_BACKEND=file",
                "BUSINESAIOS_TENANT_REGISTRY_PATH=" + str(tenant_store),
                "CONTROL_PLANE_API_KEY=",
                "SMOKE_TENANT_ID=",
                "",
            ]
        ),
        encoding="utf-8",
    )
    env_file.chmod(0o640)
    return env_file, api_store, tenant_store


def _credential(env_file: Path) -> str:
    _, values = bootstrap.read_environment_file(env_file)
    return values["CONTROL_PLANE_API_KEY"]


def test_bootstrap_binds_real_tenant_and_keeps_plaintext_only_in_private_env(tmp_path: Path) -> None:
    env_file, api_store_path, _ = _prepare(tmp_path)

    result = bootstrap.bootstrap_production_control_plane(
        tenant_id="production-smoke",
        env_file=env_file,
    )

    credential = _credential(env_file)
    assert result.tenant_id == "production-smoke"
    assert result.key_id == credential.split(".", 1)[0]
    assert bootstrap.validate_current_binding_from_environment(env_file) == result.key_id
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600

    store_payload = api_store_path.read_text(encoding="utf-8")
    assert credential not in store_payload
    assert credential.split(".", 1)[1] not in store_payload

    store = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    record = store.get(result.key_id)
    assert record is not None
    assert record.tenant_id == "production-smoke"
    assert RoleId.OWNER in record.roles
    assert "provider_control_plane" in record.scopes
    assert record.metadata["credential_kind"] == bootstrap.CREDENTIAL_KIND
    assert record.metadata["managed_by"] == bootstrap.MANAGED_BY


def test_bootstrap_refuses_unknown_or_inactive_tenant_without_mutating_env(tmp_path: Path) -> None:
    env_file, api_store_path, _ = _prepare(tmp_path, tenant_status=TenantStatus.SUSPENDED)
    original = env_file.read_text(encoding="utf-8")

    with pytest.raises(PermissionError, match="tenant is not active"):
        bootstrap.bootstrap_production_control_plane(
            tenant_id="production-smoke",
            env_file=env_file,
        )
    assert env_file.read_text(encoding="utf-8") == original
    assert not api_store_path.exists()

    with pytest.raises(KeyError, match="unknown tenant"):
        bootstrap.bootstrap_production_control_plane(
            tenant_id="missing-tenant",
            env_file=env_file,
        )
    assert env_file.read_text(encoding="utf-8") == original
    assert not api_store_path.exists()


def test_bootstrap_rotates_only_its_previous_managed_credential(tmp_path: Path) -> None:
    env_file, api_store_path, _ = _prepare(tmp_path)

    first = bootstrap.bootstrap_production_control_plane(
        tenant_id="production-smoke",
        env_file=env_file,
    )
    second = bootstrap.bootstrap_production_control_plane(
        tenant_id="production-smoke",
        env_file=env_file,
    )

    assert second.key_id != first.key_id
    assert second.rotated_key_id == first.key_id
    store = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    first_record = store.get(first.key_id)
    second_record = store.get(second.key_id)
    assert first_record is not None and first_record.is_active() is False
    assert second_record is not None and second_record.is_active() is True


def test_bootstrap_rotates_previous_managed_credential_when_smoke_tenant_changes(tmp_path: Path) -> None:
    env_file, api_store_path, tenant_store = _prepare(tmp_path)
    registry = PersistentTenantRegistry(path=tenant_store)
    registry.register(
        TenantRecord(
            tenant_id="production-smoke-next",
            display_name="Production smoke next",
            status=TenantStatus.ACTIVE,
        )
    )

    first = bootstrap.bootstrap_production_control_plane(
        tenant_id="production-smoke",
        env_file=env_file,
    )
    second = bootstrap.bootstrap_production_control_plane(
        tenant_id="production-smoke-next",
        env_file=env_file,
    )

    assert second.tenant_id == "production-smoke-next"
    assert second.rotated_key_id == first.key_id
    store = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    first_record = store.get(first.key_id)
    second_record = store.get(second.key_id)
    assert first_record is not None and first_record.is_active() is False
    assert second_record is not None and second_record.is_active() is True
    assert second_record.tenant_id == "production-smoke-next"


def test_bootstrap_never_revokes_unrelated_previous_credential(tmp_path: Path) -> None:
    env_file, api_store_path, _ = _prepare(tmp_path)
    store = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    unrelated_record, unrelated_credential = store.issue(
        tenant_id="production-smoke",
        subject="unrelated-control-plane-client",
        roles=(RoleId.OWNER,),
        scopes=("provider_control_plane",),
    )
    env_file.write_text(
        env_file.read_text(encoding="utf-8").replace(
            "CONTROL_PLANE_API_KEY=\n",
            f"CONTROL_PLANE_API_KEY={unrelated_credential}\n",
        ),
        encoding="utf-8",
    )

    result = bootstrap.bootstrap_production_control_plane(
        tenant_id="production-smoke",
        env_file=env_file,
    )

    assert result.rotated_key_id is None
    reloaded = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    preserved = reloaded.get(unrelated_record.key_id)
    assert preserved is not None and preserved.is_active() is True


def test_bootstrap_reconciles_orphaned_lifecycle_credentials(tmp_path: Path) -> None:
    env_file, api_store_path, _ = _prepare(tmp_path)
    store = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    orphan_ids: list[str] = []
    for suffix in ("one", "two"):
        record, _ = store.issue(
            tenant_id="production-smoke",
            subject=f"orphan-{suffix}",
            roles=(RoleId.OWNER,),
            scopes=("provider_control_plane",),
            metadata={
                "credential_kind": bootstrap.CREDENTIAL_KIND,
                "managed_by": bootstrap.MANAGED_BY,
            },
        )
        orphan_ids.append(record.key_id)

    result = bootstrap.bootstrap_production_control_plane(
        tenant_id="production-smoke",
        env_file=env_file,
    )

    reloaded = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    for key_id in orphan_ids:
        orphan = reloaded.get(key_id)
        assert orphan is not None and orphan.is_active() is False
    active_lifecycle = [
        record
        for record in reloaded.list_records()
        if record.is_active()
        and record.metadata.get("credential_kind") == bootstrap.CREDENTIAL_KIND
        and record.metadata.get("managed_by") == bootstrap.MANAGED_BY
    ]
    assert [record.key_id for record in active_lifecycle] == [result.key_id]


def test_persistent_api_key_store_reconciles_stale_writers_without_losing_keys(tmp_path: Path) -> None:
    store_path = tmp_path / "api-keys" / "api_keys.json"
    first_writer = PersistentApiKeyStore(path=store_path, pepper="test-production-pepper")
    stale_second_writer = PersistentApiKeyStore(path=store_path, pepper="test-production-pepper")

    first_record, _ = first_writer.issue(
        tenant_id="tenant-a",
        subject="first-writer",
        roles=(RoleId.OWNER,),
    )
    second_record, _ = stale_second_writer.issue(
        tenant_id="tenant-b",
        subject="second-writer",
        roles=(RoleId.OWNER,),
    )

    reloaded = PersistentApiKeyStore(path=store_path, pepper="test-production-pepper")
    assert reloaded.get(first_record.key_id) == first_record
    assert reloaded.get(second_record.key_id) == second_record


def test_validator_rejects_noncanonical_credential_even_when_hash_is_valid(tmp_path: Path) -> None:
    env_file, api_store_path, tenant_store = _prepare(tmp_path)
    _, values = bootstrap.read_environment_file(env_file)
    store = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    _, credential = store.issue(
        tenant_id="production-smoke",
        subject="legacy",
        roles=(RoleId.OWNER,),
        scopes=("provider_control_plane",),
    )
    values["BUSINESAIOS_TENANT_REGISTRY_PATH"] = str(tenant_store)

    with pytest.raises(RuntimeError, match="canonical production bootstrap"):
        bootstrap.validate_credential_binding(
            credential=credential,
            tenant_id="production-smoke",
            values=values,
        )


def test_validator_requires_control_plane_scope_even_for_canonical_metadata(tmp_path: Path) -> None:
    env_file, api_store_path, _ = _prepare(tmp_path)
    _, values = bootstrap.read_environment_file(env_file)
    store = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    _, credential = store.issue(
        tenant_id="production-smoke",
        subject="scope-deficient",
        roles=(RoleId.OWNER,),
        metadata={
            "credential_kind": bootstrap.CREDENTIAL_KIND,
            "managed_by": bootstrap.MANAGED_BY,
        },
    )

    with pytest.raises(RuntimeError, match="provider_control_plane scope"):
        bootstrap.validate_credential_binding(
            credential=credential,
            tenant_id="production-smoke",
            values=values,
        )


def test_cli_reports_identifiers_but_never_prints_plaintext_credential(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file, _, _ = _prepare(tmp_path)
    monkeypatch.setattr(bootstrap, "DEFAULT_ENV_FILE", env_file)
    monkeypatch.setattr(bootstrap.os, "geteuid", lambda: 0)

    assert bootstrap.main(["--tenant-id", "production-smoke"]) == 0
    output = capsys.readouterr().out
    credential = _credential(env_file)

    assert "PRODUCTION_CONTROL_PLANE_BOOTSTRAP_OK" in output
    assert credential not in output
    assert credential.split(".", 1)[1] not in output


def test_cli_rejects_environment_path_override(tmp_path: Path) -> None:
    env_file, _, _ = _prepare(tmp_path)

    with pytest.raises(SystemExit):
        bootstrap._build_parser().parse_args(
            ["--tenant-id", "production-smoke", "--env-file", str(env_file)]
        )


def test_environment_parser_and_writer_fail_closed_on_duplicate_managed_keys(tmp_path: Path) -> None:
    env_file, _, _ = _prepare(tmp_path)
    env_file.write_text(
        env_file.read_text(encoding="utf-8") + "SMOKE_TENANT_ID=duplicate\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="duplicate environment key"):
        bootstrap.bootstrap_production_control_plane(
            tenant_id="production-smoke",
            env_file=env_file,
        )


def test_host_lifecycle_is_sha_bound_and_chains_bootstrap_restart_and_canonical_verifier() -> None:
    subprocess.run(["bash", "-n", str(HOST_LIFECYCLE)], check=True)
    text = HOST_LIFECYCLE.read_text(encoding="utf-8")

    for token in (
        "EXPECTED_SHA",
        "SMOKE_TENANT_ID",
        "bootstrap_production_control_plane.py",
        "systemctl restart",
        "verify_runtime_host_contract.sh",
        'BUSINESAIOS_DEPLOY_ROOT="/opt/businesaios"',
        'PRODUCTION_ENV_FILE="/etc/businesaios/api.env"',
        'API_SERVICE="businesaios-api.service"',
        'export PYTHONPATH="$BUSINESAIOS_DEPLOY_ROOT"',
        'cd "$BUSINESAIOS_DEPLOY_ROOT"',
        'LOCAL_HEALTH_URL="http://127.0.0.1:8000/health"',
        'LOCAL_READINESS_URL="http://127.0.0.1:8000/readyz"',
        "API_READY=0",
        "attempt<=60",
        "curl -fsS --max-time 2",
        'FRONTEND_DIST="$BUSINESAIOS_DEPLOY_ROOT/frontend/dist"',
        'chmod 0755',
        'chmod 0644',
        'publish_frontend_access',
    ):
        assert token in text
    assert "${BUSINESAIOS_DEPLOY_ROOT:-" not in text
    assert "${PRODUCTION_ENV_FILE:-" not in text
    assert "${API_SERVICE:-" not in text
    assert "--env-file" not in text
    assert "deployed SHA $OBSERVED_SHA != expected SHA $EXPECTED_SHA" in text
    sha_guard_index = text.index("deployed SHA $OBSERVED_SHA != expected SHA $EXPECTED_SHA")
    publish_call_index = text.index("\npublish_frontend_access\n", sha_guard_index)
    assert sha_guard_index < publish_call_index < text.index("\"$PYTHON_BIN\" \"$BOOTSTRAP\"")
    assert text.index("\"$PYTHON_BIN\" \"$BOOTSTRAP\"") < text.index("systemctl restart")
    assert text.index("systemctl restart") < text.index("API_READY=0")
    assert text.index("API_READY=0") < text.rindex("\"$VERIFY\"")


def test_runtime_verifier_forces_privileged_smoke_through_https_ingress() -> None:
    subprocess.run(["bash", "-n", str(RUNTIME_VERIFIER)], check=True)
    text = RUNTIME_VERIFIER.read_text(encoding="utf-8")

    for token in (
        "production_ingress",
        "PUBLIC_BASE_URL",
        "BUSINESAIOS_TRUST_PROXY_HEADERS",
        "BUSINESAIOS_TRUSTED_PROXY_IPS",
        "127.0.0.1/32",
        "::1/128",
        'SMOKE_BASE_URL="$PUBLIC_BASE_URL"',
        'api_check "$PUBLIC_BASE_URL/health"',
        'api_check "$PUBLIC_BASE_URL/readyz"',
    ):
        assert token in text
    assert "PUBLIC_API_BASE" not in text
    assert 'SMOKE_BASE_URL="$LOCAL_API_BASE"' not in text
    assert "scheme.lower() != 'https'" in text
    assert "networks != expected" in text


def test_production_env_template_defines_loopback_only_tls_proxy_boundary() -> None:
    text = PRODUCTION_ENV_TEMPLATE.read_text(encoding="utf-8")

    assert "PUBLIC_BASE_URL=https://api.businessaios.ru" in text
    assert "BUSINESAIOS_TRUST_PROXY_HEADERS=true" in text
    assert "BUSINESAIOS_TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128" in text


def test_runbook_requires_expected_sha_from_trusted_release_evidence() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert 'EXPECTED_SHA="<exact-40-character-github-main-sha>"' in text
    assert 'EXPECTED_SHA="$(git -C /opt/businesaios rev-parse HEAD)"' not in text
    assert "Do not derive `EXPECTED_SHA` from the current production checkout" in text
    assert "PUBLIC_BASE_URL=https://api.businessaios.ru" in text
    assert "BUSINESAIOS_TRUST_PROXY_HEADERS=true" in text
    assert "BUSINESAIOS_TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128" in text
    assert "authenticated synthetic action over HTTPS" in text
