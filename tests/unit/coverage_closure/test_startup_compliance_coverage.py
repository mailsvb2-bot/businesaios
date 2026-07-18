from __future__ import annotations

from pathlib import Path

import pytest

from compliance.action_compliance_policy import ActionComplianceInput, ActionCompliancePolicy
from compliance.base import ComplianceControl, ComplianceVerdictStatus
from compliance.connector_compliance_matrix import (
    ConnectorComplianceMatrix,
    ConnectorComplianceRecord,
    ConnectorRiskTier,
)
from deployment.startup_barrier_policy import (
    StartupBarrierPolicy,
    StartupBarrierReport,
    StartupBarrierViolation,
)


def test_startup_barrier_covers_validation_and_path_contracts(tmp_path: Path) -> None:
    for name in ("boot", "runtime", "config", "release"):
        (tmp_path / name).mkdir()
    (tmp_path / "VERSION").write_text("1.0.0", encoding="utf-8")
    (tmp_path / "RELEASE_TAG").write_text("v1", encoding="utf-8")
    (tmp_path / "release/manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "extra.txt").write_text("ok", encoding="utf-8")

    policy = StartupBarrierPolicy(
        required_env=("TOKEN",),
        forbidden_env=("UNSAFE",),
        required_paths=("extra.txt",),
        repo_root=tmp_path,
    )
    ok = policy.validate_environment({"APP_ENV": "production", "TOKEN": "x", "RELEASE_TAG": "v1"})
    assert ok.ok and ok.summaries() == ()
    policy.assert_environment({"APP_ENV": "prod", "TOKEN": "x", "RELEASE_TAG": "v1"})

    (tmp_path / "boot").rmdir()
    (tmp_path / "runtime").rmdir()
    (tmp_path / "runtime").write_text("not-dir", encoding="utf-8")
    (tmp_path / "VERSION").unlink()
    (tmp_path / "VERSION").mkdir()
    (tmp_path / "release/manifest.json").unlink()
    report = policy.validate_environment(
        {
            "APP_ENV": "prod-ish",
            "TOKEN": "",
            "UNSAFE": "yes",
            "DEBUG": "true",
        }
    )
    codes = {item.code for item in report.violations}
    assert {
        "missing_env",
        "forbidden_env",
        "invalid_app_env",
        "missing_directory",
        "directory_expected",
        "file_expected",
    } <= codes

    prod = policy.validate_environment({"APP_ENV": "prod", "TOKEN": "x", "DEBUG": "on"})
    assert {"release_tag_required", "debug_forbidden_in_prod", "release_manifest_missing"} <= {
        item.code for item in prod.violations
    }
    with pytest.raises(RuntimeError, match="startup barrier policy failed"):
        policy.assert_environment({"APP_ENV": "prod"})
    with pytest.raises(ValueError, match="escapes"):
        policy._resolve("../escape")
    with pytest.raises(ValueError, match="must be unique"):
        StartupBarrierPolicy(required_env=("A", "A"))
    with pytest.raises(ValueError, match="code is required"):
        StartupBarrierViolation(code="", message="x")
    with pytest.raises(ValueError, match="message is required"):
        StartupBarrierViolation(code="x", message="")
    assert not StartupBarrierReport((StartupBarrierViolation("x", "bad"),)).ok


def test_action_and_connector_compliance_decision_matrix() -> None:
    policy = ActionCompliancePolicy(forbidden_action_types=("erase",), restricted_scopes=("money",))
    denied = policy.evaluate(
        ActionComplianceInput(
            action_type="",
            action_scope="",
            actor_type="agent",
            tenant_id=None,
            region=None,
            connector_name=None,
            contains_pii=True,
            contains_secrets=True,
            outbound_effect=True,
            destructive=True,
        )
    )
    assert denied.status is ComplianceVerdictStatus.DENIED
    assert not denied.allowed and not denied.operator_required
    assert {"empty_action_type", "empty_action_scope"} <= set(denied.blocked_by)
    assert ComplianceControl.APPROVAL in denied.required_controls

    forbidden = policy.evaluate(
        ActionComplianceInput("erase", "money", "human", "t", "eu", "x")
    )
    assert forbidden.blocked_by == ("forbidden_action_type",)

    operator = policy.evaluate(
        ActionComplianceInput("charge", "money", "autonomous", "t", "eu", "x", destructive=True)
    )
    assert operator.allowed and operator.operator_required
    allowed = policy.evaluate(
        ActionComplianceInput("read", "catalog", "human", "t", "eu", "x", evidence_required=False)
    )
    assert allowed.status is ComplianceVerdictStatus.ALLOWED

    matrix = ConnectorComplianceMatrix()
    unknown = matrix.evaluate(
        connector_name="missing", target_region="eu", contains_pii=False, contains_secrets=False
    )
    assert not unknown.allowed and unknown.risk_tier is ConnectorRiskTier.CRITICAL

    base = dict(
        connector_name="crm",
        risk_tier=ConnectorRiskTier.HIGH,
        regions_allowed=("EU",),
        supports_audit=True,
        supports_redaction=False,
        supports_scoped_credentials=False,
        supports_data_deletion=False,
    )
    matrix.register(ConnectorComplianceRecord(**base))
    assert matrix.get("CRM") is not None
    assert not matrix.evaluate(connector_name="crm", target_region="us", contains_pii=False, contains_secrets=False).allowed
    assert not matrix.evaluate(connector_name="crm", target_region="eu", contains_pii=False, contains_secrets=False, cross_region_transfer=True).allowed
    assert not matrix.evaluate(connector_name="crm", target_region="eu", contains_pii=True, contains_secrets=False).allowed
    assert not matrix.evaluate(connector_name="crm", target_region="eu", contains_pii=False, contains_secrets=True).allowed

    matrix.register(
        ConnectorComplianceRecord(
            **{**base, "supports_audit": False, "approved_for_pii": True, "approved_for_secrets": True}
        )
    )
    assert "audit" in matrix.evaluate(connector_name="crm", target_region=None, contains_pii=False, contains_secrets=False).reason.lower()

    matrix.register(
        ConnectorComplianceRecord(
            **{
                **base,
                "approved_for_pii": True,
                "approved_for_secrets": True,
                "approved_for_cross_region_transfer": True,
            }
        )
    )
    decision = matrix.evaluate(
        connector_name="crm",
        target_region="eu",
        contains_pii=True,
        contains_secrets=True,
        cross_region_transfer=True,
    )
    assert decision.allowed
    assert {
        ComplianceControl.PII_MINIMIZATION,
        ComplianceControl.SECRET_SCOPE_ENFORCEMENT,
        ComplianceControl.UPSTREAM_REDACTION_REQUIRED,
        ComplianceControl.RETENTION_EXCEPTION_REVIEW,
    } <= set(decision.required_controls)
