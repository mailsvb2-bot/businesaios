from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from runtime.governance.pricing_versioning import enforce_pricing_versioning_or_raise
from scripts.server import bootstrap_production_control_plane as bootstrap
from tenancy.tenant_contract import TenantRecord, TenantStatus
from tenancy.tenant_registry import PersistentTenantRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_LIFECYCLE = PROJECT_ROOT / "scripts" / "server" / "bootstrap_and_verify_production.sh"
PRODUCTION_ENV_TEMPLATE = PROJECT_ROOT / ".env.example.prod"
RUNBOOK = PROJECT_ROOT / "docs" / "operations" / "production-control-plane-bootstrap.md"


class _Log:
    def info(self, *_args: object, **_kwargs: object) -> None:
        return

    def warning(self, *_args: object, **_kwargs: object) -> None:
        return


def _prepare_bootstrap_env(tmp_path: Path) -> tuple[Path, Path]:
    api_store = tmp_path / "runtime" / "api" / "api_keys.json"
    tenant_store = tmp_path / "runtime" / "tenancy" / "tenant_registry.json"
    registry = PersistentTenantRegistry(path=tenant_store)
    registry.register(
        TenantRecord(
            tenant_id="production-smoke",
            display_name="Production smoke",
            status=TenantStatus.ACTIVE,
        )
    )
    env_file = tmp_path / "api.env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=prod",
                f"DATA_DIR={tmp_path / 'runtime'}",
                "API_CONTROL_PLANE_API_KEY_PEPPER=test-production-pepper",
                "BUSINESAIOS_API_KEY_STORE_BACKEND=file",
                f"BUSINESAIOS_API_KEY_STORE_PATH={api_store}",
                "BUSINESAIOS_TENANT_REGISTRY_BACKEND=file",
                f"BUSINESAIOS_TENANT_REGISTRY_PATH={tenant_store}",
                "CONTROL_PLANE_API_KEY=",
                "SMOKE_TENANT_ID=",
                "PRICING_VERSION=old-approved-version",
                "",
            ]
        ),
        encoding="utf-8",
    )
    env_file.chmod(0o640)
    return env_file, api_store


def test_strict_production_never_accepts_pricing_override_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override = tmp_path / "pricing-version.txt"
    override.write_text("override-would-be-a-second-authority", encoding="utf-8")
    monkeypatch.delenv("PRICING_VERSION", raising=False)
    monkeypatch.setenv("PRICING_VERSION_OVERRIDE_PATH", str(override))
    monkeypatch.setenv("PRICING_FINGERPRINT_PATH", str(tmp_path / "fingerprint.json"))

    with pytest.raises(RuntimeError, match="requires PRICING_VERSION to be set"):
        enforce_pricing_versioning_or_raise(
            pricing_config={"currency": "RUB", "price_rub": 1000},
            production_strict=True,
            log=_Log(),
        )


def test_strict_pricing_fingerprint_defaults_to_canonical_data_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRICING_VERSION", "pricing-2026-08-19")
    monkeypatch.delenv("PRICING_FINGERPRINT_PATH", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "runtime"))

    enforce_pricing_versioning_or_raise(
        pricing_config={"currency": "RUB", "price_rub": 1000},
        production_strict=True,
        log=_Log(),
    )

    assert (tmp_path / "runtime" / "governance" / "pricing_fingerprint.json").is_file()


def test_canonical_bootstrap_atomically_binds_explicit_pricing_version(tmp_path: Path) -> None:
    env_file, _ = _prepare_bootstrap_env(tmp_path)

    result = bootstrap.bootstrap_production_control_plane(
        tenant_id="production-smoke",
        env_file=env_file,
        pricing_version="pricing-2026-08-19-rub",
    )

    _, values = bootstrap.read_environment_file(env_file)
    assert values["PRICING_VERSION"] == "pricing-2026-08-19-rub"
    assert values["SMOKE_TENANT_ID"] == "production-smoke"
    assert values["CONTROL_PLANE_API_KEY"]
    assert result.pricing_version == "pricing-2026-08-19-rub"


def test_invalid_pricing_version_fails_before_credential_or_env_mutation(tmp_path: Path) -> None:
    env_file, api_store = _prepare_bootstrap_env(tmp_path)
    original = env_file.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="PROD_STRICT_PRICING_VERSION_INVALID"):
        bootstrap.bootstrap_production_control_plane(
            tenant_id="production-smoke",
            env_file=env_file,
            pricing_version="v1",
        )

    assert env_file.read_text(encoding="utf-8") == original
    assert not api_store.exists()


def test_host_lifecycle_owns_production_tenant_pricing_and_enabled_connector_readiness() -> None:
    subprocess.run(["bash", "-n", str(HOST_LIFECYCLE)], check=True)
    text = HOST_LIFECYCLE.read_text(encoding="utf-8")

    for token in (
        'APPROVED_PRICING_VERSION="${PRICING_VERSION:-}"',
        "unset SMOKE_TENANT_ID PRICING_VERSION",
        "build_default_tenant_policy_store",
        "policy_store.require(smoke_tenant)",
        "PRODUCTION_STRICT_MODE must be enabled in canonical production",
        'TELEGRAM_SERVICE="businesaios-connector-telegram.service"',
        'LOCAL_TELEGRAM_READINESS_URL="http://127.0.0.1:8088/readyz"',
        'systemctl reset-failed "$TELEGRAM_SERVICE"',
        '--pricing-version "$APPROVED_PRICING_VERSION"',
    ):
        assert token in text


def test_production_template_has_single_persistent_pricing_and_policy_surfaces() -> None:
    text = PRODUCTION_ENV_TEMPLATE.read_text(encoding="utf-8")

    for token in (
        "PRODUCTION_STRICT_MODE=1",
        "PRICING_VERSION=",
        "PRICING_FINGERPRINT_PATH=/var/lib/businesaios/runtime/governance/pricing_fingerprint.json",
        "BUSINESAIOS_TENANT_POLICY_STORE_BACKEND=file",
        "BUSINESAIOS_TENANT_POLICY_STORE_PATH=/var/lib/businesaios/runtime/tenancy/tenant_policies.json",
    ):
        assert token in text
    assert "PRICING_VERSION_OVERRIDE_PATH=" not in text


def test_runbook_requires_explicit_business_pricing_version() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert 'PRICING_VERSION="<approved-production-pricing-version>"' in text
    assert "strict production does not accept `PRICING_VERSION_OVERRIDE_PATH`" in text
    assert "derive `PRICING_VERSION` from the deployed SHA" in text
