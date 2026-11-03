"""D6 regression: application decisions and executor flags share one parser.

No live provider calls are made. An injected environment must take precedence
over process environment, and missing/unknown values remain disabled.
"""
from __future__ import annotations

import pytest

from application.business_flows import ad_spend_guard, admin, visual_creatives
from runtime.platform.config.env_flags import env_bool as runtime_env_bool
from shared.env_access import env_bool

READERS = (
    (ad_spend_guard.MUTATIONS_ENV, ad_spend_guard.mutations_enabled),
    (ad_spend_guard.PROVIDER_ENV, ad_spend_guard.provider_enabled),
    (admin.RETIRE_ENV, admin.retire_enabled),
    (visual_creatives.VIDEO_ENV, lambda env: visual_creatives.video_generation_mode(
        env, country_code="RU") == "motion"),
)
VALUES = (
    ("1", True), ("true", True), ("yes", True), ("y", True),
    ("on", True), (" On ", True), ("0", False), ("false", False),
    ("off", False), ("enabled", False), ("t", False), ("", False),
)


@pytest.mark.parametrize(("flag", "reader"), READERS)
@pytest.mark.parametrize(("value", "enabled"), VALUES)
def test_canonical_flag_parsing_matches_application_and_runtime(
    monkeypatch, flag, reader, value, enabled,
):
    monkeypatch.setenv(flag, value)
    assert runtime_env_bool is env_bool
    assert env_bool(flag, False) is enabled
    assert reader(None) is enabled
    assert reader({flag: value}) is enabled
    monkeypatch.setenv(flag, "0" if enabled else "1")
    assert env_bool(flag, False, environ={flag: value}) is enabled
    assert reader({flag: value}) is enabled


@pytest.mark.parametrize(("flag", "reader"), READERS)
def test_all_d6_flags_are_disabled_when_unset(monkeypatch, flag, reader):
    monkeypatch.delenv(flag, raising=False)
    assert env_bool(flag, False) is False
    assert reader(None) is False
    assert reader({}) is False
