from pathlib import Path


def test_idempotency_is_separate() -> None:
    assert Path("infra/idempotency.py").exists()
    assert Path("infra/idempotency_store.py").exists()
