from __future__ import annotations

import json
from pathlib import Path

from runtime.production_boot_contract import ProductionBootInput, ProductionStorageMode, evaluate_production_boot_contract
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_production_boot import run as run_production_boot


def test_production_boot_contract_passes_only_with_postgres_api_profile() -> None:
    report = evaluate_production_boot_contract(
        ProductionBootInput(
            env="production",
            app_profile="api",
            run_mode="api",
            database_url="postgresql://user:pass@postgres:5432/businesaios",
            postgres_enabled=True,
            migrations_required=True,
            release_id="test-release",
        )
    )

    assert report.passed is True
    assert report.storage_mode == ProductionStorageMode.POSTGRES_REQUIRED
    assert report.to_dict()["passed"] is True


def test_production_boot_contract_blocks_sqlite_or_disabled_postgres() -> None:
    report = evaluate_production_boot_contract(
        ProductionBootInput(
            env="production",
            app_profile="api",
            run_mode="api",
            database_url="sqlite:///data.db",
            postgres_enabled=False,
            migrations_required=True,
            release_id="test-release",
        )
    )

    assert report.passed is False
    failed = {item.name for item in report.checks if not item.passed}
    assert "postgres_enabled" in failed
    assert "database_url_is_postgres" in failed


def test_production_boot_step_writes_honest_contract_artifact() -> None:
    ok, message = run_production_boot()
    payload = json.loads(Path("artifacts/ci/production_boot.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "production_boot"
    assert payload["passed"] is True
    assert payload["storage_mode"] == "postgres_required"
    assert payload["contract_only"] is True
    assert payload["live_database_connection"] is False
    assert payload["reason"] == "production boot contract proof without live DB credentials"


def test_release_plans_include_production_boot_before_release_artifacts() -> None:
    for gate in ("production-boot", "release", "pre-release"):
        steps = [item.name for item in plan_for_gate(gate).steps]
        assert "production-boot" in steps

    release_steps = [item.name for item in plan_for_gate("release").steps]
    assert release_steps.index("production-boot") < release_steps.index("verify-release")
    assert release_steps.index("production-boot") < release_steps.index("build-artifact")
