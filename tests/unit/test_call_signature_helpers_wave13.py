from core.events.read_call import call_iter_events, call_latest_events
from runtime.boot.outbound_constructor import build_with_supported_kwargs
from runtime.decision_input.provider_call import call_decision_input_provider


def test_call_iter_events_zero_arg_supported_without_masking_internal_bug():
    calls = []

    def zero_arg():
        calls.append('ok')
        return [{'k': 1}]

    out = list(call_iter_events(iter_fn=zero_arg, tenant_id='t', allow_zero_arg_fallback=True))
    assert out == [{'k': 1}]
    assert calls == ['ok']


def test_call_latest_events_internal_type_error_is_not_treated_as_legacy_signature():
    def broken(*, tenant_id, event_types, limit):
        raise TypeError('internal bug')

    try:
        list(call_latest_events(latest_fn=broken, tenant_id='t', event_types=('x',), limit=10))
    except TypeError as exc:
        assert 'internal bug' in str(exc)
    else:
        raise AssertionError('expected TypeError to propagate')


def test_outbound_constructor_filters_unsupported_kwargs_before_call():
    captured = {}

    class Queue:
        def __init__(self, *, global_rps, max_queue):
            captured['global_rps'] = global_rps
            captured['max_queue'] = max_queue

    obj = build_with_supported_kwargs(
        constructor=Queue,
        kwargs={'global_rps': 1.0, 'max_queue': 5, 'unknown': 'drop'},
    )
    assert isinstance(obj, Queue)
    assert captured == {'global_rps': 1.0, 'max_queue': 5}


def test_decision_input_provider_prefers_full_runtime_packet_when_supported():
    seen = {}

    def build_fn(*, world_state, proposal, generated_at_ms, safe_mode):
        seen['proposal'] = proposal
        seen['safe_mode'] = safe_mode
        return {'ok': True}

    out = call_decision_input_provider(
        build_fn=build_fn,
        world_state={'x': 1},
        proposal={'a': 1},
        generated_at_ms=7,
        safe_mode=True,
    )
    assert out == {'ok': True}
    assert seen == {'proposal': {'a': 1}, 'safe_mode': True}
