from canon.canon_ai_enforcer import run_enforcer


def test_canon_ai_enforcer_runs():
    report = run_enforcer(".")
    assert report is not None
    assert hasattr(report, "violations")
    assert hasattr(report, "ok")
