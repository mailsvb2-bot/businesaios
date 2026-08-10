from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from execution.action_catalog import get_action_spec
from runtime._internal.effects_clients.visual_gateway_client import visual_gateway_json
from runtime._internal.effects_domains.visual_creative_gateway import (
    assert_visual_creative_binding,
    visual_creative_evidence,
    visual_creative_idempotency_key,
    visual_creative_job_payload,
)
from runtime.boot.actions_registry import get_spec as get_runtime_spec
from runtime.execution.evidence_trust import extract_trusted_router_evidence
from runtime.firewall.process_guard import ProcessCapabilityError
from runtime.handlers.visual_creative_gateway import handle_generate_visual_creative, handle_poll_visual_creative
from runtime.security.capability_gate import GuardedEffectsPort, clear_effect_capability, set_effect_capability


def _job(**overrides):
    value = {"id": "j1", "provider": "yandexart", "scope_id": "tenant-1", "kind": "image", "status": "queued", "model": "m1", "asset_ready": False}
    value.update(overrides)
    return visual_creative_job_payload(value)


def test_job_payload_rejects_invalid_gateway_shape_and_non_boolean_readiness() -> None:
    with pytest.raises(RuntimeError, match="invalid_response"):
        visual_creative_job_payload({"id": "j1", "scope_id": "tenant-1", "kind": "image", "status": "queued"})
    with pytest.raises(RuntimeError, match="invalid_response"):
        visual_creative_job_payload({"id": "j1", "scope_id": "tenant-1", "kind": "image", "status": "succeeded", "asset_ready": "false"})


def test_job_payload_rejects_unsafe_identifier_and_scope() -> None:
    with pytest.raises(RuntimeError, match="invalid_job"):
        visual_creative_job_payload({"id": "../escape", "scope_id": "tenant-1", "kind": "image", "status": "queued", "asset_ready": False})
    with pytest.raises(RuntimeError, match="invalid_job"):
        visual_creative_job_payload({"id": "j1", "scope_id": "../escape?", "kind": "image", "status": "queued", "asset_ready": False})


def test_succeeded_job_requires_ready_asset() -> None:
    with pytest.raises(RuntimeError, match="inconsistent_completion"):
        _job(status="succeeded", asset_ready=False)
    evidence = visual_creative_evidence(tenant_id="tenant-1", job=_job(status="succeeded", asset_ready=True))
    assert evidence["code"] == "visual_creative_completed"
    assert evidence["payload"]["asset_ready"] is True


def test_job_acceptance_evidence_is_trusted_but_does_not_claim_completion() -> None:
    evidence = visual_creative_evidence(tenant_id="tenant-1", job=_job())
    assert evidence["source"] == "connector"
    assert evidence["payload"]["connector"] == "visual_creative_gateway"
    assert evidence["verified"] is True
    assert evidence["code"] == "visual_creative_job_accepted"
    assert evidence["payload"]["asset_ready"] is False
    assert extract_trusted_router_evidence({"router_evidence": evidence}) == evidence


def test_failed_job_is_not_verified() -> None:
    evidence = visual_creative_evidence(tenant_id="tenant-1", job=_job(status="failed", error_code="provider_failed"))
    assert evidence["verified"] is False
    assert evidence["external_refs"] == []


def test_visual_binding_mismatches_fail_closed() -> None:
    job = _job()
    assert_visual_creative_binding(tenant_id="tenant-1", job=job, expected_kind="image", expected_job_id="j1")
    with pytest.raises(RuntimeError, match="scope_mismatch"):
        assert_visual_creative_binding(tenant_id="tenant-2", job=job)
    with pytest.raises(RuntimeError, match="kind_mismatch"):
        assert_visual_creative_binding(tenant_id="tenant-1", job=job, expected_kind="video")
    with pytest.raises(RuntimeError, match="job_id_mismatch"):
        assert_visual_creative_binding(tenant_id="tenant-1", job=job, expected_job_id="j2")


def test_visual_idempotency_is_stable_and_tenant_scoped() -> None:
    first = visual_creative_idempotency_key(tenant_id="tenant-1", decision_id="d1", kind="image")
    assert first == visual_creative_idempotency_key(tenant_id="tenant-1", decision_id="d1", kind="image")
    assert first != visual_creative_idempotency_key(tenant_id="tenant-2", decision_id="d1", kind="image")
    assert first != visual_creative_idempotency_key(tenant_id="tenant-1", decision_id="d2", kind="image")
    assert first != visual_creative_idempotency_key(tenant_id="tenant-1", decision_id="d1", kind="video")


def test_visual_gateway_auth_fails_closed_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISUAL_GATEWAY_URL", "https://visual-gateway.example")
    monkeypatch.delenv("VISUAL_GATEWAY_TOKEN", raising=False)
    monkeypatch.delenv("VISUAL_GATEWAY_ALLOW_ANONYMOUS", raising=False)
    with pytest.raises(RuntimeError, match="token_not_configured"):
        visual_gateway_json("GET", "/v1/creative/generations/j1", {"scope_id": "tenant-1"})


def test_generate_and_poll_handlers_are_thin() -> None:
    effects = Mock()
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d1", correlation_id="c1"))
    handle_generate_visual_creative({"tenant_id": "tenant-1", "user_id": "u1", "kind": "image", "prompt": "city", "duration_seconds": 7}, effects, env)
    assert effects.generate_visual_creative.call_args.kwargs["decision_id"] == "d1"
    assert effects.generate_visual_creative.call_args.kwargs["prompt"] == "city"
    handle_poll_visual_creative({"tenant_id": "tenant-1", "user_id": "u1", "job_id": "j1"}, effects, env)
    assert effects.poll_visual_creative.call_args.kwargs["job_id"] == "j1"


def test_guarded_effects_forwards_visual_calls_only_with_capability() -> None:
    impl = Mock()
    guarded = GuardedEffectsPort(token="visual-token", impl=impl)
    clear_effect_capability()
    with pytest.raises(ProcessCapabilityError):
        guarded.generate_visual_creative(tenant_id="tenant-1")
    set_effect_capability("visual-token")
    try:
        guarded.generate_visual_creative(tenant_id="tenant-1")
        guarded.poll_visual_creative(job_id="j1")
    finally:
        clear_effect_capability()
    impl.generate_visual_creative.assert_called_once_with(tenant_id="tenant-1")
    impl.poll_visual_creative.assert_called_once_with(job_id="j1")


def test_visual_actions_are_known_and_keep_canonical_execution_contracts() -> None:
    generate, poll = get_action_spec("visual_creative_generate@v1"), get_action_spec("visual_creative_poll@v1")
    assert generate.decisionable and generate.routable and generate.executable
    assert generate.approval_required and generate.bounded_by_blast_radius
    assert poll.decisionable and poll.routable and poll.executable and poll.action_class == "read_only"
    runtime_generate, runtime_poll = get_runtime_spec("visual_creative_generate@v1"), get_runtime_spec("visual_creative_poll@v1")
    assert runtime_generate.execution_category == "external_effect"
    assert runtime_generate.external_confirmation_mode == "required"
    assert runtime_generate.requires_idempotency_key is True
    assert runtime_poll.execution_category == "advisory"
    assert runtime_poll.external_confirmation_mode == "not_required"
    assert runtime_poll.requires_idempotency_key is True
