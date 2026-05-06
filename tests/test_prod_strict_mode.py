import os
import sys


def test_prod_strict_blocks_demo(monkeypatch):
    from runtime import bootstrap as bs

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("RUN_MODE", "demo")
    monkeypatch.setenv("RELEASE_ATTEST", "0")

    # main.py entrypoint is required; keep it valid here.
    monkeypatch.setattr(sys, "argv", ["main.py"])
    try:
        bs.bootstrap()
        assert False, "expected strict mode to block demo"
    except RuntimeError as e:
        assert "PROD_STRICT_RUN_MODE" in str(e)


def test_prod_strict_blocks_alt_entrypoint(monkeypatch):
    from runtime import bootstrap as bs

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("RUN_MODE", "telegram")
    monkeypatch.setenv("RELEASE_ATTEST", "0")
    monkeypatch.setattr(sys, "argv", ["other_entry.py"])
    try:
        bs.bootstrap()
        assert False, "expected strict mode to block non-main entrypoint"
    except RuntimeError as e:
        assert "PROD_STRICT_ENTRYPOINT" in str(e)


def test_non_prod_allows_demo(monkeypatch):
    from runtime import bootstrap as bs

    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("RUN_MODE", "demo")
    monkeypatch.setenv("RELEASE_ATTEST", "0")
    monkeypatch.setattr(sys, "argv", ["whatever.py"])
    # Should not raise.
    bs.bootstrap()
