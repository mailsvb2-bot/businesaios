from core.retention.feature_extractors.activity import apply_activity_features
from core.retention.feature_extractors.audio import apply_audio_features
from core.retention.feature_extractors.mood import mood10_to_bucket


class _Store:
    def iter_events(self, **kwargs):
        return []

    def latest_events(self, **kwargs):
        return []


def test_retention_helpers_are_callable():
    vec = {}
    apply_audio_features(vec=vec, events=[], tenant_id="t1", user_id="u1")
    apply_activity_features(vec=vec, events=[], store=_Store(), tenant_id="t1", user_id="u1")
    assert mood10_to_bucket(9) == 4
    assert vec["listen_ratio_d1"] == 0.0
