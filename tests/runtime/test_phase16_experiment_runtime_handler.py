from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.actions.names import ACTION_CREATE_EXPERIMENT_V1
from core.actions.catalog import build_schema_registry
from core.experiments.errors import ExperimentValidationError
from core.experiments.repositories.event_store_repository import EventStoreExperimentRepository
from execution.runners.internal.create_experiment import Runner as LegacyCreateExperimentRunner
from runtime.boot.actions_registry import get_spec, handler_actions
from runtime.execution.execution_contract_lock import verify_execution_contract
from runtime.handlers.experiments_create import handle_create_experiment
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _env(*, decision_id="decision-exp-1", business_id="business-1"):
    return SimpleNamespace(
        decision=SimpleNamespace(
            action=ACTION_CREATE_EXPERIMENT_V1,
            decision_id=decision_id,
            correlation_id="corr-exp-1",
            issuer_id="businesaios-core",
            contract_v2={"business_id": business_id},
        )
    )


def _payload(**overrides):
    payload = {
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "name": "Autonomous bounded experiment",
        "hypothesis": "Treatment improves conversion without harming complaints",
        "primary_metric": "conversion_rate",
        "minimum_sample_size": 100,
        "duration_days": 14,
        "overlap_keys": ["offer:main"],
    }
    payload.update(overrides)
    return payload


def test_create_experiment_is_registered_on_canonical_runtime_action_surface():
    spec = get_spec(ACTION_CREATE_EXPERIMENT_V1)
    assert ACTION_CREATE_EXPERIMENT_V1 in handler_actions()
    assert spec.execution_category == "internal_bookkeeping"
    assert spec.external_confirmation_mode == "not_required"
    assert spec.requires_idempotency_key is True
    schema_registry = build_schema_registry()
    assert schema_registry.latest_version(ACTION_CREATE_EXPERIMENT_V1) == 1
    assert schema_registry.validate(
        ACTION_CREATE_EXPERIMENT_V1,
        {
            "tenant_id": "tenant-1",
            "business_id": "business-1",
            "name": "Experiment",
            "hypothesis": "Treatment improves the primary metric",
        },
        version=1,
    ) == 1


def test_governed_runtime_handler_persists_real_experiment():
    store = MemoryEventStore()
    result = handle_create_experiment(_payload(), None, _env(), event_store=store)

    plan = EventStoreExperimentRepository(
        store,
        tenant_id="tenant-1",
        business_id="business-1",
    ).get(result["experiment_id"])

    assert plan is not None
    assert result["ok"] is True
    assert result["status"] == "verified"
    assert result["experiment_status"] == "active"
    assert result["policy_governed"] is True
    assert plan.hypothesis == _payload()["hypothesis"]
    assert plan.duration_days == 14
    state_event = list(
        store.iter_events(
            tenant_id="tenant-1",
            event_type="experiment.state_changed@v1",
        )
    )[0]
    assert state_event["decision_id"] == "decision-exp-1"
    assert state_event["correlation_id"] == "corr-exp-1"


def test_same_authorized_decision_is_idempotent():
    store = MemoryEventStore()
    first = handle_create_experiment(_payload(), None, _env(), event_store=store)
    second = handle_create_experiment(_payload(), None, _env(), event_store=store)

    assert second["experiment_id"] == first["experiment_id"]
    events = list(
        store.iter_events(
            tenant_id="tenant-1",
            event_type="experiment.state_changed@v1",
        )
    )
    assert len(events) == 1


def test_same_decision_cannot_mutate_authorized_experiment_parameters():
    store = MemoryEventStore()
    handle_create_experiment(_payload(), None, _env(), event_store=store)

    with pytest.raises(ValueError, match="identity collision"):
        handle_create_experiment(
            _payload(hypothesis="different treatment after authorization"),
            None,
            _env(),
            event_store=store,
        )


def test_runtime_handler_rejects_business_identity_drift():
    store = MemoryEventStore()
    with pytest.raises(PermissionError, match="BUSINESS_ID_MISMATCH"):
        handle_create_experiment(
            _payload(business_id="business-forged"),
            None,
            _env(business_id="business-1"),
            event_store=store,
        )


def test_legacy_internal_runner_fails_closed():
    with pytest.raises(RuntimeError, match="CANONICAL_RUNTIME_ACTION"):
        LegacyCreateExperimentRunner().run(object())


@pytest.mark.parametrize("field", ["minimum_sample_size", "duration_days"])
def test_runtime_handler_rejects_explicit_zero_limits(field):
    store = MemoryEventStore()
    with pytest.raises(ExperimentValidationError):
        handle_create_experiment(
            _payload(**{field: 0}),
            None,
            _env(),
            event_store=store,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("subject_key", "", "subject_key"),
        ("audience_key", "", "audience_key"),
        ("owner", "", "owner"),
    ],
)
def test_runtime_handler_does_not_replace_explicit_blank_identity_fields(field, value, message):
    store = MemoryEventStore()
    with pytest.raises(ExperimentValidationError, match=message):
        handle_create_experiment(
            _payload(**{field: value}),
            None,
            _env(),
            event_store=store,
        )


@pytest.mark.parametrize(("field", "message"), [("variants", "variants must be a list"), ("metrics", "metrics must be a list")])
def test_runtime_handler_does_not_replace_explicit_null_structures(field, message):
    store = MemoryEventStore()
    with pytest.raises(ValueError, match=message):
        handle_create_experiment(
            _payload(**{field: None}),
            None,
            _env(),
            event_store=store,
        )


def test_runtime_execution_verification_accepts_persisted_internal_experiment():
    store = MemoryEventStore()
    env = _env()
    env.decision.payload = _payload()
    env.decision.issued_at_ms = 1_750_000_000_000
    output = handle_create_experiment(
        env.decision.payload,
        None,
        env,
        event_store=store,
    )

    verified = verify_execution_contract(
        executor=SimpleNamespace(_reliability=None, _evidence_verifier=None),
        env=env,
        output=output,
    )

    assert verified.verified is True
    assert verified.verification["status"] == "verified"
