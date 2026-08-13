from __future__ import annotations

import pytest

from bootstrap import prod_guards


def _prod(monkeypatch: pytest.MonkeyPatch, profile: str = "telegram") -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("PRODUCTION_STRICT_MODE", "1")
    monkeypatch.setenv("RUN_MODE", profile)
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    monkeypatch.delenv("ADMIN_IDS", raising=False)


def test_zero_admins_remains_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod(monkeypatch)
    with pytest.raises(RuntimeError, match="GOVERNANCE_ADMIN_REQUIRED"):
        prod_guards.enforce_two_admins_in_prod_or_explain()


def test_one_admin_is_valid_for_prod_telegram(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod(monkeypatch)
    monkeypatch.setenv("ADMIN_USER_IDS", "123456789")
    prod_guards.enforce_two_admins_in_prod_or_explain()


def test_one_admin_is_valid_for_prod_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod(monkeypatch, "webhook")
    monkeypatch.setenv("ADMIN_USER_IDS", "123456789")
    prod_guards.enforce_two_admins_in_prod_or_explain()


def test_admin_alias_accepts_one_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod(monkeypatch)
    monkeypatch.setenv("ADMIN_IDS", "123456789")
    prod_guards.enforce_two_admins_in_prod_or_explain()


def test_admin_ids_are_deduplicated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_USER_IDS", "123, 123, ,456,123")
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    assert prod_guards._normalized_admin_ids() == ("123", "456")
