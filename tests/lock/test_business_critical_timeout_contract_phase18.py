from __future__ import annotations

from scripts.ci import step_business_critical_tests as step


def test_business_critical_gate_has_current_runtime_budget(monkeypatch) -> None:
    captured = {}

    def fake_run_pytest_with_report(**kwargs):
        captured.update(kwargs)
        return True, "ok"

    monkeypatch.setattr(step, "run_pytest_with_report", fake_run_pytest_with_report)
    ok, message = step.run()

    assert ok is True
    assert message == "business critical invariant gate passed"
    assert captured["target_args"] == ["tests/business_critical"]
    assert captured["timeout"] == 600
