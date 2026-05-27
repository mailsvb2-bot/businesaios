from __future__ import annotations

from pathlib import Path

import pytest

_ALLOWED = {
    "runtime/_internal/effect_types.py",
    "runtime/_internal/effect_router.py",
    "runtime/_internal/effect_payloads.py",
    "tests/runtime/test_effect_router_registry_audit.py",
    "tests/runtime/test_effect_action_type_registry.py",
    "tests/arch/test_lock_effect_action_type_literals.py",
    "tests/execution/test_canonical_execution_feedback_contract.py",
    "tests/execution/test_headless_closed_loop_runtime_bridge.py",
    "tests/execution/test_headless_step_execution_feedback.py",
    "tests/execution/test_verification_vocabulary_bridge.py",
    "tests/integration/test_effect_verification_bridge.py",
    "tests/runtime/test_effect_evidence_contract.py",
    "tests/runtime/test_effect_result_contracts.py",
    "tests/runtime/test_effect_router_result_normalization.py",
}

_CANONICAL_LITERALS = (
    '"telegram.send_message"',
    '"telegram.send_audio"',
    '"telegram.answer_callback"',
    '"telegram.send_chat_action"',
    '"telegram.self_check"',
    '"telegram.poll_updates"',
    '"payments.yookassa.create"',
    '"payments.yookassa.get_status"',
    '"crm.write_record"',
    '"ads.update_budget"',
    '"website.publish_page"',
    '"weather.open_meteo.current"',
    '"llm.marketing_complete"',
)


@pytest.mark.lock
def test_lock_canonical_effect_action_literals_are_centralized() -> None:
    root = Path(__file__).resolve().parents[2]
    bad: list[str] = []
    for py in root.rglob("*.py"):
        rel = py.relative_to(root).as_posix()
        if rel.startswith((".venv/", "venv/", "build/", "dist/", "__pycache__/")):
            continue
        if rel in _ALLOWED:
            continue
        txt = py.read_text(encoding="utf-8", errors="ignore")
        for literal in _CANONICAL_LITERALS:
            if literal in txt:
                bad.append(f"{rel} -> {literal}")
                break
    assert not bad, (
        "Canonical effect action literals must live only in effect_types/router/tests:\n"
        + "\n".join(sorted(bad))
    )
