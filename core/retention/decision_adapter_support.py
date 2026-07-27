from __future__ import annotations

import logging
from typing import Any

from core.observability.errors import log_exception_throttled
from core.observability.throttled_logger import exception_throttled
from core.policies.telegram.helpers import ProposedAction, normalize_proposed_action, propose
from core.retention.decision_debug import build_retention_debug
from core.retention.decision_steps import make_telemetry_step, offer_allowed, render_offer_step
from core.retention.engine import RetentionEvaluation, RetentionOfferCandidate, materialize_candidate
from core.tenancy.normalization import normalize_tenant_id

log = logging.getLogger(__name__)
_TELEGRAM_TEXT_LIMIT = 4096


def read_outbound_metrics(*, reader: Any, logger: Any) -> dict:
    try:
        return dict(reader() or {})
    except Exception:
        log_exception_throttled(
            logger or log,
            key="retention.outbound_metrics",
            msg="retention: outbound metrics read failed",
            throttle_ms=30_000,
        )
        return {}


def read_entitlements_from_state(*, state: Any, logger: Any) -> Any:
    try:
        economy = getattr(state, "economy", None)
        if isinstance(economy, dict):
            return economy.get("entitlements")
    except Exception:
        log_exception_throttled(
            logger or log,
            key="retention.entitlements",
            msg="retention: failed to read entitlements from state.economy",
            throttle_ms=60_000,
        )
    return None


def decorate_retention_payload(*, payload: dict, user_id: str, key: str, msg: str) -> dict:
    try:
        from core.retention.telemetry import with_retention_telemetry

        return with_retention_telemetry(payload, user_id=user_id)
    except Exception:
        exception_throttled(log, key=f"{key}|{user_id}", msg=msg)
        return payload


def build_initial_plan(*, decision: Any, user_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compatibility telemetry plan; it never contains an offer effect."""

    debug = build_retention_debug(decision)
    step = make_telemetry_step(decision=decision, user_id=user_id)
    step["payload"] = decorate_retention_payload(
        payload=step["payload"],
        user_id=user_id,
        key="retention.telemetry.decorate",
        msg="retention: failed to decorate telemetry payload",
    )
    return [step], debug


def merge_inline_keyboards(base: Any, offer: Any) -> dict | None:
    base_markup = dict(base) if isinstance(base, dict) else {}
    offer_markup = dict(offer) if isinstance(offer, dict) else {}
    if not base_markup:
        return offer_markup or None
    if not offer_markup:
        return base_markup or None
    base_rows = base_markup.get("inline_keyboard")
    offer_rows = offer_markup.get("inline_keyboard")
    if not isinstance(base_rows, list) or not isinstance(offer_rows, list):
        return offer_markup
    merged = dict(base_markup)
    merged["inline_keyboard"] = [*base_rows, *offer_rows]
    return merged


def _max_band(state: Any) -> str | None:
    constraints = getattr(state, "price_constraints", None)
    if not isinstance(constraints, dict):
        return None
    value = constraints.get("max_band")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _safe_mode_blocks(*, state: Any, arm: str) -> tuple[bool, str]:
    constraints = getattr(state, "price_constraints", None)
    if not isinstance(constraints, dict):
        return False, ""
    if str(constraints.get("mode") or "").strip().lower() != "safe":
        return False, ""
    prefixes = constraints.get("disallow_offer_prefixes")
    if not isinstance(prefixes, (list, tuple)):
        return False, ""
    blocked = any(isinstance(prefix, str) and str(arm).startswith(prefix) for prefix in prefixes)
    return blocked, str(constraints.get("reason") or "safe_mode") if blocked else ""


def _combined_text(*, base_text: str, offer_text: str) -> str | None:
    first = str(base_text or "")
    second = str(offer_text or "").strip()
    if not second:
        return None
    combined = f"{first}\n\n{second}" if first else second
    return combined if len(combined) <= _TELEGRAM_TEXT_LIMIT else None


def _tracking_payload(
    *,
    base_payload: dict[str, Any],
    offer_track_payload: dict[str, Any],
    candidate: RetentionOfferCandidate,
    evaluation: RetentionEvaluation,
    user_id: str,
) -> dict[str, Any]:
    payload = dict(offer_track_payload)
    payload.update(
        {
            "tenant_id": evaluation.tenant_id,
            "candidate_id": candidate.candidate_id,
            "decision_owner": "DecisionCore",
            "retention_reason": evaluation.reason,
            "ranking_evidence": {
                "expected_profit_delta_minor": candidate.expected_profit_delta_minor,
                "ope_wis": candidate.ope_wis,
                "uplift": candidate.uplift,
                "risk_penalty": candidate.risk_penalty,
                "propensity": candidate.propensity,
            },
        }
    )
    base_event_type = base_payload.get("track_event_type")
    base_event_payload = base_payload.get("track_payload")
    if isinstance(base_event_type, str) and base_event_type.strip():
        payload["additional_track_events"] = [
            {
                "event_type": base_event_type.strip(),
                "payload": dict(base_event_payload) if isinstance(base_event_payload, dict) else {},
            }
        ]
    return decorate_retention_payload(
        payload=payload,
        user_id=user_id,
        key="retention.telemetry.decorate_track",
        msg="retention: failed to decorate offer_shown track payload",
    )


def build_offer_proposal(
    *,
    base: ProposedAction | dict[str, Any],
    evaluation: RetentionEvaluation,
    candidate: RetentionOfferCandidate,
    state: Any,
    offer_engine: Any,
    cooldown_store: Any,
    user_id: str,
) -> ProposedAction | None:
    """Build one complete candidate action without selecting or writing state."""

    normalized = normalize_proposed_action(base)
    if normalized.action != "send_message@v1":
        return None
    tenant_id = normalize_tenant_id(
        getattr(state, "tenant_id", None),
        fallback=str(evaluation.tenant_id or "").strip(),
    )
    if not tenant_id:
        return None
    blocked, _reason = _safe_mode_blocks(state=state, arm=candidate.offer_arm)
    if blocked:
        return None
    if not offer_allowed(
        offer_engine=offer_engine,
        cooldown_store=cooldown_store,
        state=state,
        tenant_id=tenant_id,
        user_id=user_id,
        offer_id=candidate.offer_arm,
    ):
        return None

    selected = materialize_candidate(evaluation, candidate_id=candidate.candidate_id)
    offer_step, _meta = render_offer_step(
        offer_engine=offer_engine,
        state=state,
        decision=selected,
        user_id=user_id,
        max_band=_max_band(state),
    )
    combined_text = _combined_text(
        base_text=str(normalized.payload.get("text") or ""),
        offer_text=str(offer_step.get("fallback_text") or ""),
    )
    if combined_text is None:
        return None

    payload = dict(normalized.payload)
    payload.update(
        {
            "tenant_id": tenant_id,
            "user_id": str(payload.get("user_id") or user_id),
            "text": combined_text,
            "reply_markup": merge_inline_keyboards(
                payload.get("reply_markup"),
                offer_step.get("reply_markup"),
            ),
            "track_event_type": "offer_shown",
            "track_payload": _tracking_payload(
                base_payload=normalized.payload,
                offer_track_payload=(
                    dict(offer_step.get("track_payload"))
                    if isinstance(offer_step.get("track_payload"), dict)
                    else {}
                ),
                candidate=candidate,
                evaluation=evaluation,
                user_id=user_id,
            ),
        }
    )
    return propose(
        "send_message@v1",
        payload,
        ranking={
            "expected_profit_delta_minor": candidate.expected_profit_delta_minor,
            "ope_wis": candidate.ope_wis,
            "uplift": candidate.uplift,
            "risk_penalty": candidate.risk_penalty,
        },
    )


def try_build_offer_step(
    *,
    decision: Any,
    state: Any,
    offer_engine: Any,
    cooldown_store: Any,
    user_id: str,
) -> tuple[dict | None, dict[str, Any] | None]:
    """Legacy explicit-decision renderer without pre-execution cooldown writes."""

    if (
        decision.suppressed
        or not decision.offer_arm
        or decision.offer_arm == "NONE"
        or decision.offer_price_rub is None
    ):
        return None, None
    tenant_id = normalize_tenant_id(
        getattr(state, "tenant_id", None),
        fallback=str(decision.tenant_id or "").strip(),
    )
    if not tenant_id:
        debug = dict(decision.debug or {})
        debug.setdefault("constraints", {})["reason"] = "missing_tenant_id"
        return None, debug
    blocked, reason = _safe_mode_blocks(state=state, arm=str(decision.offer_arm))
    if blocked:
        debug = dict(decision.debug or {})
        debug.setdefault("constraints", {})["reason"] = reason
        return None, debug
    if not offer_allowed(
        offer_engine=offer_engine,
        cooldown_store=cooldown_store,
        state=state,
        tenant_id=tenant_id,
        user_id=user_id,
        offer_id=str(decision.offer_arm),
    ):
        return None, None
    step, _meta = render_offer_step(
        offer_engine=offer_engine,
        state=state,
        decision=decision,
        user_id=user_id,
        max_band=_max_band(state),
    )
    step["track_payload"] = decorate_retention_payload(
        payload=dict(step.get("track_payload") or {}),
        user_id=user_id,
        key="retention.telemetry.decorate_track",
        msg="retention: failed to decorate offer_shown track payload",
    )
    return step, None
