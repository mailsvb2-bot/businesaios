from __future__ import annotations

import inspect
import sys
from dataclasses import replace
from itertools import product
from pathlib import Path
from types import ModuleType

import pytest

from runtime.execution.crash_window_recovery_contract import (
    CrashWindowRecoveryAction,
    ExecutionCrashWindowState,
    required_recovery_action,
)
from runtime.platform.postgres_contract import (
    REQUIRED_MIGRATIONS,
    REQUIRED_SCHEMA_OBJECTS,
    PostgresRuntimeProof,
    evaluate_postgres_contract,
)
from runtime.platform.postgres_live_probe import run_postgres_live_probe
from security.key_provider import InMemoryKeyProvider
from security.request_signing import RequestSigner


def _model_recovery_action(
    ledger_marked: bool,
    dispatch_claimed: bool,
    handler_dispatched: bool,
    effect_verified: bool,
) -> CrashWindowRecoveryAction:
    if effect_verified and not handler_dispatched:
        return CrashWindowRecoveryAction.BLOCK_INVALID_STATE
    if handler_dispatched and not dispatch_claimed:
        return CrashWindowRecoveryAction.BLOCK_INVALID_STATE
    if dispatch_claimed and not ledger_marked:
        return CrashWindowRecoveryAction.BLOCK_INVALID_STATE
    if not ledger_marked:
        return CrashWindowRecoveryAction.BLOCK_INVALID_STATE
    if effect_verified:
        return CrashWindowRecoveryAction.NOOP_ALREADY_VERIFIED
    if handler_dispatched:
        return CrashWindowRecoveryAction.VERIFY_OR_RETRY_DISPATCH
    return CrashWindowRecoveryAction.REPLAY_DISPATCH


def _state(flags: tuple[bool, bool, bool, bool]) -> ExecutionCrashWindowState:
    ledger_marked, dispatch_claimed, handler_dispatched, effect_verified = flags
    return ExecutionCrashWindowState(
        decision_id="wave-e-decision",
        idempotency_key="wave-e-idempotency",
        ledger_marked=ledger_marked,
        dispatch_claimed=dispatch_claimed,
        handler_dispatched=handler_dispatched,
        effect_verified=effect_verified,
    )


def test_wave_e_property_model_exhausts_crash_window_state_space() -> None:
    for flags in product((False, True), repeat=4):
        state = _state(flags)
        assert required_recovery_action(state) is _model_recovery_action(*flags)


def test_wave_e_malformed_fuzz_corpus_fails_closed() -> None:
    malformed_ids = ("", " ", "\t", "\n", "\r\n", "\x00", "\x7f", "\x85", "\u200b")
    for malformed in malformed_ids:
        state = replace(_state((True, False, False, False)), decision_id=malformed)
        assert required_recovery_action(state) is CrashWindowRecoveryAction.BLOCK_INVALID_STATE
        state = replace(_state((True, False, False, False)), idempotency_key=malformed)
        assert required_recovery_action(state) is CrashWindowRecoveryAction.BLOCK_INVALID_STATE

    signer = RequestSigner(key_provider=InMemoryKeyProvider())
    payload = {"tenant_id": "tenant-a", "operation": "charge", "amount": 10}
    envelope = signer.sign(payload=payload, tenant_id="tenant-a")
    structurally_invalid = (
        replace(envelope, key_id=""),
        replace(envelope, algorithm=""),
        replace(envelope, signature=""),
        replace(envelope, content_digest=""),
    )
    for candidate in structurally_invalid:
        with pytest.raises(ValueError):
            signer.verify(payload=payload, envelope=candidate)

    cryptographically_invalid = (
        replace(envelope, algorithm="hmac-sha256:v999"),
        replace(envelope, signature="not-a-valid-signature"),
        replace(envelope, content_digest="0" * 64),
    )
    for candidate in cryptographically_invalid:
        assert signer.verify(payload=payload, envelope=candidate) is False

    for value in malformed_ids:
        fuzz_payload = {"tenant_id": "tenant-a", "operation": "charge", "value": value}
        signed = signer.sign(payload=fuzz_payload, tenant_id="tenant-a")
        tampered = {**fuzz_payload, "value": value + "x"}
        assert signer.verify(payload=tampered, envelope=signed) is False


def test_wave_e_fault_recovery_contract_blocks_invalid_and_recovers_valid_states() -> None:
    expected = {
        (True, False, False, False): CrashWindowRecoveryAction.REPLAY_DISPATCH,
        (True, True, False, False): CrashWindowRecoveryAction.REPLAY_DISPATCH,
        (True, True, True, False): CrashWindowRecoveryAction.VERIFY_OR_RETRY_DISPATCH,
        (True, True, True, True): CrashWindowRecoveryAction.NOOP_ALREADY_VERIFIED,
        (False, False, False, False): CrashWindowRecoveryAction.BLOCK_INVALID_STATE,
        (False, True, False, False): CrashWindowRecoveryAction.BLOCK_INVALID_STATE,
        (True, False, True, False): CrashWindowRecoveryAction.BLOCK_INVALID_STATE,
        (True, True, False, True): CrashWindowRecoveryAction.BLOCK_INVALID_STATE,
    }
    for flags, action in expected.items():
        assert required_recovery_action(_state(flags)) is action


def _load_mutant(source: str, *, mutation_name: str) -> ModuleType:
    module_name = f"_wave_e_recovery_mutant_{mutation_name}"
    module = ModuleType(module_name)
    module.__file__ = f"<{module_name}>"
    sys.modules[module_name] = module
    try:
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_wave_e_targeted_mutation_testing_kills_critical_recovery_mutants() -> None:
    source_path = Path(inspect.getsourcefile(required_recovery_action) or "")
    source = source_path.read_text(encoding="utf-8")
    mutations = {
        "drop_ledger_guard": (
            "    if not ledger_marked:\n        return CrashWindowRecoveryAction.BLOCK_INVALID_STATE\n",
            "    if False and not ledger_marked:\n        return CrashWindowRecoveryAction.BLOCK_INVALID_STATE\n",
        ),
        "drop_verified_branch": (
            "    if effect_verified:\n        return CrashWindowRecoveryAction.NOOP_ALREADY_VERIFIED\n",
            "    if False and effect_verified:\n        return CrashWindowRecoveryAction.NOOP_ALREADY_VERIFIED\n",
        ),
        "drop_dispatched_branch": (
            "    if handler_dispatched:\n        return CrashWindowRecoveryAction.VERIFY_OR_RETRY_DISPATCH\n",
            "    if False and handler_dispatched:\n        return CrashWindowRecoveryAction.VERIFY_OR_RETRY_DISPATCH\n",
        ),
        "break_replay_action": (
            "    return CrashWindowRecoveryAction.REPLAY_DISPATCH\n",
            "    return CrashWindowRecoveryAction.BLOCK_INVALID_STATE\n",
        ),
    }
    corpus = tuple(product((False, True), repeat=4))
    for mutation_name, (needle, replacement) in mutations.items():
        assert needle in source, f"mutation seam drifted: {mutation_name}"
        mutant = _load_mutant(source.replace(needle, replacement, 1), mutation_name=mutation_name)
        killed = False
        for flags in corpus:
            mutant_state = mutant.ExecutionCrashWindowState(
                decision_id="wave-e-decision",
                idempotency_key="wave-e-idempotency",
                ledger_marked=flags[0],
                dispatch_claimed=flags[1],
                handler_dispatched=flags[2],
                effect_verified=flags[3],
            )
            actual = mutant.required_recovery_action(mutant_state).value
            if actual != _model_recovery_action(*flags).value:
                killed = True
                break
        assert killed, f"critical mutant survived: {mutation_name}"


def _postgres_runtime_proof(*, outbox_roundtrip_ok: bool) -> PostgresRuntimeProof:
    return PostgresRuntimeProof(
        database_url_present=True,
        postgres_enabled=True,
        psycopg_available=True,
        live_probe_ok=True,
        schema_objects_present=REQUIRED_SCHEMA_OBJECTS,
        migrations_applied=REQUIRED_MIGRATIONS,
        event_store_roundtrip_ok=True,
        outbox_roundtrip_ok=outbox_roundtrip_ok,
        recovery_contract_ok=True,
        rollback_roundtrip_ok=True,
        backup_evidence_ok=True,
        ledger_chain_verification_ok=True,
    )


def test_wave_e_postgres_race_proof_is_mandatory_for_ready_runtime_contract() -> None:
    live_probe_source = Path(inspect.getsourcefile(run_postgres_live_probe) or "").read_text(encoding="utf-8")
    assert "outbox_roundtrip_ok=outbox_state_ok and outbox_concurrency_ok" in live_probe_source

    ready = evaluate_postgres_contract(_postgres_runtime_proof(outbox_roundtrip_ok=True))
    assert ready["status"] == "ready"

    concurrent_idempotency_failed = evaluate_postgres_contract(_postgres_runtime_proof(outbox_roundtrip_ok=False))
    assert concurrent_idempotency_failed["status"] == "blocked"
    assert "postgres_outbox_roundtrip_required" in concurrent_idempotency_failed["violations"]
