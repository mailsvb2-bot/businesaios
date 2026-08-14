from __future__ import annotations

import pytest

from bootstrap.prod_guards import enforce_two_admins_in_prod_or_explain


def _set_prod(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    for key in ('ADMIN_USER_IDS', 'ADMIN_IDS', 'TELEGRAM_WEBHOOK_ENABLED', 'TELEGRAM_USE_WEBHOOK'):
        monkeypatch.delenv(key, raising=False)
    env = {
        'APP_ENV': 'prod',
        'PRODUCTION_STRICT_MODE': '1',
        'RUN_MODE': 'telegram',
        'GOVERNANCE_ADMIN_MODE': 'single_owner',
        'ALLOW_SELF_APPROVE': '0',
        **overrides,
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize(
    ('mode', 'admins', 'self_approve', 'error'),
    [
        ('single_owner', '123456789', '0', None),
        ('single_owner', '', '0', 'GOVERNANCE_SINGLE_OWNER_REQUIRED'),
        *[('single_owner', value, '0', 'GOVERNANCE_ADMIN_IDS_INVALID') for value in ('0', '-1', 'owner', '12x')],
        ('single_owner', '123456789,987654321', '0', 'GOVERNANCE_SINGLE_OWNER_REQUIRED'),
        ('single_owner', '123456789', '1', 'GOVERNANCE_SELF_APPROVE_FORBIDDEN'),
        ('dual_control', '123456789,123456789', '0', 'GOVERNANCE_TWO_ADMINS_REQUIRED'),
        ('dual_control', '123456789,987654321', '0', None),
        ('unknown', '123456789', '0', 'GOVERNANCE_ADMIN_MODE_INVALID'),
    ],
)
def test_production_admin_topology(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    admins: str,
    self_approve: str,
    error: str | None,
) -> None:
    _set_prod(monkeypatch, GOVERNANCE_ADMIN_MODE=mode, ALLOW_SELF_APPROVE=self_approve, ADMIN_USER_IDS=admins)
    if error:
        with pytest.raises(RuntimeError, match=error):
            enforce_two_admins_in_prod_or_explain()
    else:
        enforce_two_admins_in_prod_or_explain()


@pytest.mark.parametrize('webhook_enabled,error', [('1', 'GOVERNANCE_SINGLE_OWNER_REQUIRED'), ('0', None)])
def test_api_profile_uses_explicit_webhook_activation(
    monkeypatch: pytest.MonkeyPatch,
    webhook_enabled: str,
    error: str | None,
) -> None:
    _set_prod(monkeypatch, RUN_MODE='api', TELEGRAM_WEBHOOK_ENABLED=webhook_enabled, ADMIN_USER_IDS='')
    if error:
        with pytest.raises(RuntimeError, match=error):
            enforce_two_admins_in_prod_or_explain()
    else:
        enforce_two_admins_in_prod_or_explain()
