from __future__ import annotations

import pytest

from bootstrap.prod_guards import enforce_two_admins_in_prod_or_explain


def _set_prod(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    env = {
        'APP_ENV': 'prod',
        'PRODUCTION_STRICT_MODE': '1',
        'RUN_MODE': 'telegram',
        'GOVERNANCE_ADMIN_MODE': 'single_owner',
        'ALLOW_SELF_APPROVE': '0',
    }
    env.update(overrides)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('ADMIN_IDS', raising=False)
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
    monkeypatch.delenv('TELEGRAM_WEBHOOK_ENABLED', raising=False)
    monkeypatch.delenv('TELEGRAM_USE_WEBHOOK', raising=False)


def test_single_owner_accepts_one_positive_telegram_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod(monkeypatch)
    monkeypatch.setenv('ADMIN_USER_IDS', '123456789')

    enforce_two_admins_in_prod_or_explain()


@pytest.mark.parametrize('admin', ['', '0', '-1', 'owner', '12x'])
def test_single_owner_rejects_missing_or_invalid_telegram_user_id(
    monkeypatch: pytest.MonkeyPatch,
    admin: str,
) -> None:
    _set_prod(monkeypatch)
    if admin:
        monkeypatch.setenv('ADMIN_USER_IDS', admin)
    else:
        monkeypatch.delenv('ADMIN_USER_IDS', raising=False)

    expected = 'GOVERNANCE_SINGLE_OWNER_REQUIRED' if not admin else 'GOVERNANCE_ADMIN_IDS_INVALID'
    with pytest.raises(RuntimeError, match=expected):
        enforce_two_admins_in_prod_or_explain()


def test_single_owner_rejects_multiple_admins(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod(monkeypatch)
    monkeypatch.setenv('ADMIN_USER_IDS', '123456789,987654321')

    with pytest.raises(RuntimeError, match='GOVERNANCE_SINGLE_OWNER_REQUIRED'):
        enforce_two_admins_in_prod_or_explain()


def test_single_owner_still_forbids_self_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod(monkeypatch, ALLOW_SELF_APPROVE='1')
    monkeypatch.setenv('ADMIN_USER_IDS', '123456789')

    with pytest.raises(RuntimeError, match='GOVERNANCE_SELF_APPROVE_FORBIDDEN'):
        enforce_two_admins_in_prod_or_explain()


def test_dual_control_requires_two_distinct_valid_admins(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod(monkeypatch, GOVERNANCE_ADMIN_MODE='dual_control')
    monkeypatch.setenv('ADMIN_USER_IDS', '123456789,123456789')

    with pytest.raises(RuntimeError, match='GOVERNANCE_TWO_ADMINS_REQUIRED'):
        enforce_two_admins_in_prod_or_explain()

    monkeypatch.setenv('ADMIN_USER_IDS', '123456789,987654321')
    enforce_two_admins_in_prod_or_explain()


def test_api_webhook_profile_enforces_single_owner_when_telegram_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_prod(
        monkeypatch,
        RUN_MODE='api',
        TELEGRAM_BOT_TOKEN='bot-token',
        TELEGRAM_WEBHOOK_ENABLED='1',
    )
    monkeypatch.delenv('ADMIN_USER_IDS', raising=False)

    with pytest.raises(RuntimeError, match='GOVERNANCE_SINGLE_OWNER_REQUIRED'):
        enforce_two_admins_in_prod_or_explain()


def test_api_profile_without_active_telegram_provider_skips_telegram_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_prod(monkeypatch, RUN_MODE='api', TELEGRAM_WEBHOOK_ENABLED='1')
    monkeypatch.delenv('ADMIN_USER_IDS', raising=False)

    enforce_two_admins_in_prod_or_explain()
