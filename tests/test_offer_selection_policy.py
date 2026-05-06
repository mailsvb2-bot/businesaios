from core.offers.selection_policy import clamp_band, choose_band, choose_slot


def test_offer_selection_policy_prefers_audio_reengagement_and_premium_band():
    behavior = {"audio_starts": 2, "audio_completions": 1, "clicks_total": 12}
    assert choose_slot(behavior=behavior) == "default_menu" or choose_slot(behavior={"audio_starts":2,"audio_completions":0}) == "reengage_audio"
    assert choose_band(behavior=behavior) == "premium"
    assert clamp_band("premium", "standard") == "standard"
