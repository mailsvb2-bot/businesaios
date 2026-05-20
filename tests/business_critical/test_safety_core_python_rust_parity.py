from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from application.business_autonomy.safety_core import evaluate_golden_case


FIXTURE_PATH = Path("safety_fixtures/businessaios_safety_core_golden.json")
CRATE_MANIFEST = Path("rust/businessaios_safety_core/Cargo.toml")


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is required for Rust safety parity")
def test_python_and_rust_safety_core_match_golden_fixtures_exactly() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    completed = subprocess.run(
        [
            "cargo",
            "run",
            "--manifest-path",
            str(CRATE_MANIFEST),
            "--quiet",
            "--bin",
            "safety_fixture_runner",
            "--",
            "--json",
            str(FIXTURE_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    rust_report = json.loads(completed.stdout)
    assert rust_report["passed"] is True

    rust_by_name = {item["name"]: item for item in rust_report["cases"]}
    assert set(rust_by_name) == {case["name"] for case in payload["cases"]}

    for case in payload["cases"]:
        python_verdict = evaluate_golden_case(case)
        rust_verdict = rust_by_name[case["name"]]
        assert rust_verdict["allowed"] is python_verdict.allowed, case["name"]
        assert rust_verdict["reason"] == python_verdict.reason, case["name"]
        assert rust_verdict["passed"] is True, case["name"]
