from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict
from collections.abc import Iterable

from core.actions.action_names import ADS_APPLY_EXECUTE_V1
from core.ads.autopilot.contract import EXPECTED_DECISION_ISSUER
from kernel.decisioning.route_contract import canonical_runtime_route


def check_autopilot_prerequisites(*, engine: Any, tenant_id: str) -> str | None:
    ent = engine._ent.get_ads_entitlements(tenant_id)

    if getattr(ent.mode, "value", ent.mode) != engine._mode_value:
        return "ads.mode is not AUTOPILOT"

    if not engine._trust.allow_autopilot(
        tenant_id=tenant_id,
        threshold=engine._cfg.trust_threshold,
    ):
        engine._sink.emit(
            tenant_id=tenant_id,
            user_id=None,
            event_type="ads_autopilot_blocked",
            payload={
                "reason": "trust_below_threshold",
                "threshold": engine._cfg.trust_threshold,
            },
        )
        return "blocked: trust below threshold"

    if engine._cfg.breaker_enabled and engine._breaker.is_tripped(tenant_id=tenant_id):
        engine._sink.emit(
            tenant_id=tenant_id,
            user_id=None,
            event_type="ads_autopilot_blocked",
            payload={"reason": "circuit_breaker_tripped"},
        )
        return "blocked: circuit breaker tripped"

    if engine._proposal_gateway is None:
        engine._sink.emit(
            tenant_id=tenant_id,
            user_id=None,
            event_type="ads_autopilot_blocked",
            payload={"reason": "proposal_gateway_missing"},
        )
        return "blocked: proposal gateway is required"

    if engine._apply is not None:
        engine._sink.emit(
            tenant_id=tenant_id,
            user_id=None,
            event_type="ads_autopilot_blocked",
            payload={"reason": "direct_apply_forbidden"},
        )
        return "blocked: direct apply is forbidden; queue proposals via gateway"

    return None


def import_stats_window(*, engine: Any, tenant_id: str, platform: str, account_id: str) -> tuple[int, date, date]:
    df = date.today() - timedelta(days=int(engine._cfg.import_days))
    dt = date.today()
    engine._sink.emit(
        tenant_id=tenant_id,
        user_id=None,
        event_type="ads_autopilot_run_start",
        payload={
            "platform": platform,
            "account_id": account_id,
            "import_days": engine._cfg.import_days,
        },
    )
    return int(df.toordinal()), df, dt


def build_apply_payload(
    *,
    tenant_id: str,
    platform: str,
    account_id: str,
    recommendation: Any,
    source_decision_id: str,
    source_correlation_id: str,
    source_issuer_id: str,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "platform": platform,
        "account_id": account_id,
        "recommendation": (
            recommendation
            if isinstance(recommendation, dict)
            else getattr(recommendation, "__dict__", {"repr": repr(recommendation)})
        ),
        "source": "ads_autopilot",
        "mode": "guarded",
        "decision_id": str(source_decision_id),
        "correlation_id": str(source_correlation_id),
        "issuer_id": str(source_issuer_id),
        "route": canonical_runtime_route("GrowthAutopilot", "ProposalGateway"),
    }


def queue_recommendations(
    *,
    engine: Any,
    tenant_id: str,
    platform: str,
    account_id: str,
    recs: Iterable[Any],
    decision_id: str,
    correlation_id: str,
    issuer_id: str,
) -> dict[str, int]:
    if not str(decision_id or "").strip():
        raise ValueError("decision_id is required for guarded autopilot queueing")
    if not str(correlation_id or "").strip():
        raise ValueError("correlation_id is required for guarded autopilot queueing")
    if not str(issuer_id or "").strip():
        raise ValueError("issuer_id is required for guarded autopilot queueing")
    if str(issuer_id) != EXPECTED_DECISION_ISSUER:
        raise ValueError(f"issuer_id must be {EXPECTED_DECISION_ISSUER!r} for guarded autopilot queueing")

    rec_list = list(recs) if not isinstance(recs, list) else recs
    proposed = len(rec_list)

    engine._sink.emit(
        tenant_id=tenant_id,
        user_id=None,
        event_type="ads_autopilot_recs_proposed",
        payload={"count": proposed},
    )

    applied = 0
    blocked = 0
    queued = 0

    for r in rec_list[: int(engine._cfg.max_applies_per_run)]:
        payload = build_apply_payload(
            tenant_id=tenant_id,
            platform=platform,
            account_id=account_id,
            recommendation=r,
            source_decision_id=decision_id,
            source_correlation_id=correlation_id,
            source_issuer_id=issuer_id,
        )
        proposal_id = str(
            engine._proposal_gateway.propose(
                tenant_id=tenant_id,
                action=ADS_APPLY_EXECUTE_V1,
                payload=payload,
            )
            or ""
        )
        queued += 1

        engine._sink.emit(
            tenant_id=tenant_id,
            user_id=None,
            event_type="ads_autopilot_apply_queued",
            payload={
                "proposal_id": proposal_id,
                "action": ADS_APPLY_EXECUTE_V1,
                "recommendation_id": getattr(r, "id", None),
                "decision_id": str(decision_id),
                "correlation_id": str(correlation_id),
            },
        )

    return {
        "applied": applied,
        "blocked": blocked,
        "queued": queued,
        "proposed": proposed,
    }
