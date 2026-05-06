from pathlib import Path


def test_dependency_health_is_separate() -> None:
    assert Path("infra/dependency_health.py").exists()
    assert Path("infra/readiness_gates.py").exists()
