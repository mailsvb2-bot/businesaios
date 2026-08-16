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


def test_validator_rejects_noncanonical_credential_even_when_hash_is_valid(tmp_path: Path) -> None:
    env_file, api_store_path, tenant_store = _prepare(tmp_path)
    _, values = bootstrap.read_environment_file(env_file)
    store = PersistentApiKeyStore(path=api_store_path, pepper="test-production-pepper")
    _, credential = store.issue(
        tenant_id="production-smoke",
        subject="legacy",
        roles=(RoleId.OWNER,),
    )
    values["BUSINESAIOS_TENANT_REGISTRY_PATH"] = str(tenant_store)

    with pytest.raises(RuntimeError, match="canonical production bootstrap"):
        bootstrap.validate_credential_binding(
            credential=credential,
            tenant_id="production-smoke",
            values=values,
        )


def test_cli_reports_identifiers_but_never_prints_plaintext_credential(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file, _, _ = _prepare(tmp_path)

    assert bootstrap.main(["--tenant-id", "production-smoke", "--env-file", str(env_file)]) == 0
    output = capsys.readouterr().out
    credential = _credential(env_file)

    assert "PRODUCTION_CONTROL_PLANE_BOOTSTRAP_OK" in output
    assert credential not in output
    assert credential.split(".", 1)[1] not in output


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
    ):
        assert token in text
    assert "deployed SHA $OBSERVED_SHA != expected SHA $EXPECTED_SHA" in text
    assert text.index("\"$PYTHON_BIN\" \"$BOOTSTRAP\"") < text.index("systemctl restart")
    assert text.index("systemctl restart") < text.rindex("\"$VERIFY\"")
