from core.autopilot.onboarding.schema import Diagnostics
from core.autopilot.onboarding.state_machine import (
    OnboardingSession,
    OnboardingStep,
    advance_with_callback,
    session_to_settings,
)


def test_ads_connect_selection_is_persisted_in_session() -> None:
    sess = OnboardingSession(stage=OnboardingStep.CONNECT_ADS, goal="profit_7d", diag=Diagnostics(), channel="external")
    out = advance_with_callback(sess, "autopilot:ads_connect:meta")
    assert out is not None
    assert out.session.stage == OnboardingStep.READY_LAUNCH
    assert out.session.ads_platform == "meta"
    assert session_to_settings(out.session)["autopilot:session"]["ads_platform"] == "meta"


def test_external_channel_goes_through_connect_ads_step() -> None:
    sess = OnboardingSession(stage=OnboardingStep.PICK_CHANNEL, goal="profit_7d", diag=Diagnostics())
    out = advance_with_callback(sess, "autopilot:pick_channel:external")
    assert out is not None
    assert out.session.stage == OnboardingStep.CONNECT_ADS
    assert out.session.channel == "external"
    assert out.reply_markup is not None
