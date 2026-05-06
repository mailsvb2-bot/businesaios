from pathlib import Path


def test_retention_engine_split_into_helpers():
    engine = Path("core/retention/engine.py").read_text(encoding="utf-8")
    assert "from .arms import" in engine
    assert "from .pricing_flow import" in engine
    assert "from .scoring import" in engine
    assert len(engine.splitlines()) < 260
