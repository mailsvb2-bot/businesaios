from __future__ import annotations

import importlib

from core.events.store_call import call_append_event
from core.growth.event_iter_call import iter_events_range


class _StoreWithCommit:
    def __init__(self) -> None:
        self.calls = []

    def append_event(self, event, *, commit: bool) -> None:
        self.calls.append((event, commit))


class _StoreLegacy:
    def __init__(self) -> None:
        self.calls = []

    def append_event(self, event) -> None:
        self.calls.append(event)


class _RangeStore:
    def iter_events(self, *, tenant_id, event_types, start_ms, end_ms, limit):
        yield {
            'tenant_id': tenant_id,
            'event_type': event_types[0],
            'timestamp_ms': start_ms,
            'payload': {},
        }


class _LegacyRangeStore:
    def iter_events(self, *, tenant_id, event_type, start_ms, end_ms, user_id):
        yield {
            'tenant_id': tenant_id,
            'event_type': event_type,
            'timestamp_ms': start_ms,
            'payload': {},
        }


def test_call_append_event_preserves_supported_signature() -> None:
    modern = _StoreWithCommit()
    call_append_event(append_fn=modern.append_event, event_dict={'x': 1}, commit=True)
    assert modern.calls == [({'x': 1}, True)]

    legacy = _StoreLegacy()
    call_append_event(append_fn=legacy.append_event, event_dict={'x': 2}, commit=False)
    assert legacy.calls == [{'x': 2}]


def test_iter_events_range_preserves_supported_signature() -> None:
    modern = list(iter_events_range(iter_fn=_RangeStore().iter_events, tenant_id='t1', event_type='purchase', start_ms=1, end_ms=2, limit=3))
    legacy = list(iter_events_range(iter_fn=_LegacyRangeStore().iter_events, tenant_id='t1', event_type='purchase', start_ms=1, end_ms=2, limit=3))
    assert modern[0]['event_type'] == 'purchase'
    assert legacy[0]['event_type'] == 'purchase'


def test_new_synthetic_support_packages_import_and_expose_modules() -> None:
    module_names = [
        'runtime.platform.support.serving.serving_router',
        'runtime.platform.support.serving.api.handlers',
        'runtime.platform.support.serving.batch.batch_scoring_job',
        'runtime.platform.support.serving.runtime.feature_fetcher',
        'runtime.platform.support.explainability.reward_explainer',
        'runtime.platform.support.training.strategies.curriculum_manager',
        'runtime.platform.support.rollout.monitoring.rollout_health',
    ]
    for module_name in module_names:
        module = importlib.import_module(module_name)
        module_file = getattr(module, '__file__', '')
        assert module_file.startswith('<synthetic:') or module_file.endswith('.py')

    import runtime.platform.support.explainability as explainability
    import runtime.platform.support.rollout.monitoring as monitoring
    import runtime.platform.support.serving as serving
    import runtime.platform.support.training.strategies as strategies

    assert serving.serving_router.ServingRouter
    assert explainability.reward_explainer.RewardExplainer
    assert strategies.curriculum_manager.CurriculumManager
    assert monitoring.rollout_health.RolloutHealth
