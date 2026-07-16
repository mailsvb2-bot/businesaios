from __future__ import annotations

from types import SimpleNamespace

from runtime.execution.execution_contract_lock import _build_action_payload


def _env(*, action: str, payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action=action,
            payload=dict(payload),
            issued_at_ms=1_750_000_000_000,
        )
    )


def test_ads_dry_run_does_not_require_external_confirmation() -> None:
    action = _build_action_payload(
        env=_env(action="ads_apply_execute@v1", payload={"dry_run": True}),
        output={"ads_apply_status": "dry_run", "ok": True},
    )

    assert action["action_category"] == "external_effect"
    assert action["external_confirmation_mode"] == "not_required"


def test_ads_non_actuation_outcome_does_not_require_provider_confirmation() -> None:
    action = _build_action_payload(
        env=_env(action="ads_apply_execute@v1", payload={"dry_run": False}),
        output={"ads_apply_status": "blocked", "ok": True},
    )

    assert action["external_confirmation_mode"] == "not_required"


def test_ads_applied_outcome_requires_provider_confirmation() -> None:
    action = _build_action_payload(
        env=_env(action="ads_apply_execute@v1", payload={"dry_run": False}),
        output={"ads_apply_status": "applied", "ok": True},
    )

    assert action["external_confirmation_mode"] == "required"


def test_ads_unknown_non_dry_run_outcome_fails_closed_to_required() -> None:
    action = _build_action_payload(
        env=_env(action="ads_apply_execute@v1", payload={"dry_run": False}),
        output={"ok": True},
    )

    assert action["external_confirmation_mode"] == "required"


def test_offer_patch_preview_does_not_require_mutation_confirmation() -> None:
    action = _build_action_payload(
        env=_env(action="apply_offer_patch@v1", payload={"mode": "dry_run"}),
        output={"ok": True, "status": "dry_run", "mode": "dry_run"},
    )

    assert action["action_category"] == "external_effect"
    assert action["external_confirmation_mode"] == "not_required"


def test_offer_patch_apply_and_rollback_require_ledger_confirmation() -> None:
    for mode in ("apply", "rollback"):
        action = _build_action_payload(
            env=_env(action="apply_offer_patch@v1", payload={"mode": mode}),
            output={"ok": True, "status": "verified", "mode": mode},
        )

        assert action["action_category"] == "external_effect"
        assert action["external_confirmation_mode"] == "required"


def test_offer_patch_unknown_mutating_mode_fails_closed_to_required() -> None:
    action = _build_action_payload(
        env=_env(action="apply_offer_patch@v1", payload={"mode": "mystery"}),
        output={"ok": True, "status": "verified"},
    )

    assert action["external_confirmation_mode"] == "required"


def test_offer_suggestion_without_notification_remains_advisory_only() -> None:
    action = _build_action_payload(
        env=_env(action="suggest_offer_patch@v1", payload={}),
        output={"ok": True, "status": "advisory"},
    )

    assert action["action_category"] == "external_effect"
    assert action["external_confirmation_mode"] == "not_required"


def test_offer_suggestion_notification_requires_connector_confirmation() -> None:
    action = _build_action_payload(
        env=_env(
            action="suggest_offer_patch@v1",
            payload={"notify_user_id": "owner-1"},
        ),
        output={"ok": True, "status": "verified"},
    )

    assert action["action_category"] == "external_effect"
    assert action["external_confirmation_mode"] == "required"


def test_best_effort_callback_preserves_non_blocking_ux_contract() -> None:
    action = _build_action_payload(
        env=_env(action="answer_callback@v1", payload={}),
        output={"ok": True, "meta": {"mode": "best_effort", "delivered": False}},
    )

    assert action["action_category"] == "external_best_effort"
    assert action["external_confirmation_mode"] == "not_required"


def test_pytest_offline_transport_noop_preserves_headless_smoke(monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_headless_smoke")
    action = _build_action_payload(
        env=_env(action="send_message@v1", payload={}),
        output={
            "ok": False,
            "meta": {
                "mode": "noop",
                "reason": "TELEGRAM_BOT_TOKEN_MISSING",
            },
        },
    )

    assert action["external_confirmation_mode"] == "not_required"


def test_offline_transport_marker_is_not_a_production_bypass(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    action = _build_action_payload(
        env=_env(action="send_message@v1", payload={}),
        output={
            "ok": False,
            "meta": {
                "mode": "noop",
                "reason": "TELEGRAM_BOT_TOKEN_MISSING",
            },
        },
    )

    assert action["external_confirmation_mode"] == "required"
