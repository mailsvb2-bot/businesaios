from __future__ import annotations

from pathlib import Path

from tools.architecture_bypass_scanner import scan


def _findings(
    tmp_path: Path,
    source: str,
    *,
    relative: str = "application/sample.py",
) -> tuple:
    root = tmp_path / "repo"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")
    return scan(root)


def test_non_http_verify_flags_are_not_tls_bypasses(
    tmp_path: Path,
) -> None:
    findings = _findings(
        tmp_path,
        "RetryContext(verify=False)\n"
        "ConnectorCapabilities(verify=False)\n",
    )

    assert findings == ()


def test_requests_verify_false_is_blocked(tmp_path: Path) -> None:
    findings = _findings(
        tmp_path,
        "import requests\n"
        "requests.get('https://example.test', verify=False)\n",
    )

    assert "unsafe_requests_verify_false" in {
        finding.code for finding in findings
    }


def test_session_verify_false_is_blocked(tmp_path: Path) -> None:
    findings = _findings(
        tmp_path,
        "def load(session):\n"
        "    return session.get('https://example.test', verify=False)\n",
    )

    assert [finding.code for finding in findings] == [
        "unsafe_requests_verify_false"
    ]


def test_bound_redis_eval_is_not_builtin_eval(tmp_path: Path) -> None:
    findings = _findings(
        tmp_path,
        "def run(client, script):\n"
        "    return client.eval(script, 0)\n",
    )

    assert findings == ()


def test_builtin_eval_is_blocked(tmp_path: Path) -> None:
    findings = _findings(
        tmp_path,
        "def run(payload):\n"
        "    return eval(payload)\n",
    )

    assert [finding.code for finding in findings] == [
        "raw_eval_exec"
    ]


def test_explicit_stdlib_late_import_is_allowed(
    tmp_path: Path,
) -> None:
    findings = _findings(
        tmp_path,
        "sqlite3 = __import__('sqlite3')\n"
        "datetime = __import__('datetime')\n",
    )

    assert findings == ()


def test_project_late_import_remains_blocked(tmp_path: Path) -> None:
    findings = _findings(
        tmp_path,
        "module = __import__('application.hidden_owner')\n",
    )

    assert [finding.code for finding in findings] == [
        "dynamic_import_outside_owner"
    ]


def test_approval_workflow_compatibility_alias_is_not_decision_core(
    tmp_path: Path,
) -> None:
    findings = _findings(
        tmp_path,
        "def resolve(workflow, approval_decision):\n"
        "    resolver = workflow.decide\n"
        "    return resolver(approval_decision)\n",
        relative="runtime/execution/governance_runtime.py",
    )

    assert findings == ()


def test_same_decide_reference_outside_governance_remains_blocked(
    tmp_path: Path,
) -> None:
    findings = _findings(
        tmp_path,
        "def bind(workflow):\n"
        "    return workflow.decide\n",
        relative="application/feature.py",
    )

    assert [finding.code for finding in findings] == [
        "decision_authority_reference_outside_owner"
    ]
