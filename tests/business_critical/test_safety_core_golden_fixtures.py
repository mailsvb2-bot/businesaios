from __future__ import annotations

import json
from pathlib import Path

from application.business_autonomy.safety_core import evaluate_golden_case


def test_python_safety_core_matches_shared_golden_fixtures() -> None:
    payload = json.loads(Path("safety_fixtures/businessaios_safety_core_golden.json").read_text(encoding="utf-8"))
    assert payload["version"] == "businessaios_safety_core_golden.v1"
    for case in payload["cases"]:
        verdict = evaluate_golden_case(case)
        expected = case["expected"]
        assert verdict.allowed is bool(expected["allowed"]), case["name"]
        assert verdict.reason == expected["reason"], case["name"]
