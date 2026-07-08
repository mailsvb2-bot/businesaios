from __future__ import annotations

from pathlib import Path

from tools import canon_audit


def test_canon_audit_public_report_contract_on_current_repo() -> None:
    report = canon_audit.run_operational_canon_checks(Path.cwd())

    assert report.passed is True
    assert float(report.raw_score_100) >= 90.0
    assert float(report.admission_score_100) >= 90.0
    assert isinstance(report.violations, tuple)
    assert isinstance(report.hard_gates, tuple)
    assert report.hard_gates


def test_canon_audit_hard_gate_contract_is_stable() -> None:
    report = canon_audit.run_operational_canon_checks(Path.cwd())

    gate_names = {gate.gate_name for gate in report.hard_gates}

    assert {
        "no_bypass_routes",
        "no_di_container",
        "no_dynamic_magic",
        "no_hidden_logic",
        "no_noops",
    }.issubset(gate_names)
    assert all(isinstance(gate.passed, bool) for gate in report.hard_gates)
    assert all(isinstance(gate.message, str) and gate.message for gate in report.hard_gates)


def test_canon_audit_violations_are_machine_readable() -> None:
    report = canon_audit.run_operational_canon_checks(Path.cwd())

    for violation in report.violations:
        assert isinstance(violation.code, str)
        assert isinstance(violation.path, str)
        assert isinstance(violation.message, str)


def test_canon_audit_report_scores_are_bounded() -> None:
    report = canon_audit.run_operational_canon_checks(Path.cwd())

    assert 0.0 <= float(report.raw_score_100) <= 100.0
    assert 0.0 <= float(report.admission_score_100) <= 100.0
    assert report.admission_score_100 <= report.raw_score_100
