from types import SimpleNamespace

from runtime.execution.executor_bindings import apply_executor_state


class _Executor:
    pass


def test_apply_executor_state_binds_canonical_attributes():
    executor = _Executor()
    state = SimpleNamespace(
        ports=SimpleNamespace(
            guard="guard",
            handlers="handlers",
            event_log="events",
            policy_registry="registry",
            reward_engine="reward",
            learning_system="learning",
            decision_core="core",
        ),
        infra=SimpleNamespace(effect_outbox="outbox"),
        archive="archive",
        constitution="constitution",
        economic_layer="economic_layer",
        snapshot_store="snapshot_store",
        max_meta_depth=3,
        cap_token="cap_token",
        effects="effects",
    )

    apply_executor_state(executor=executor, state=state)

    assert executor._guard == "guard"
    assert executor._handlers == "handlers"
    assert executor._events == "events"
    assert executor._policy_registry == "registry"
    assert executor._reward == "reward"
    assert executor._learning == "learning"
    assert executor._decision_core == "core"
    assert executor._runtime_infra == state.infra
    assert executor._outbox == "outbox"
    assert executor._archive == "archive"
    assert executor._constitution == "constitution"
    assert executor._economic_layer == "economic_layer"
    assert executor._snapshot_store == "snapshot_store"
    assert executor._max_meta_depth == 3
    assert executor._cap_token == "cap_token"
    assert executor._effects == "effects"
