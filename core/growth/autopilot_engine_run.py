from __future__ import annotations

from core.growth.autopilot_flow import (
    check_autopilot_prerequisites,
    import_stats_window,
    queue_recommendations,
)


async def run_autopilot_engine(
    engine,
    *,
    tenant_id: str,
    platform: str,
    account_id: str,
    decision_id: str,
    correlation_id: str,
    issuer_id: str,
):
    prereq = check_autopilot_prerequisites(engine=engine, tenant_id=tenant_id)
    if prereq is not None:
        return False, prereq, {"proposed": 0, "queued": 0, "applied": 0, "blocked": 1}

    _rows, df, dt = import_stats_window(
        engine=engine,
        tenant_id=tenant_id,
        platform=platform,
        account_id=account_id,
    )
    if hasattr(engine._ads, "import_stats"):
        await engine._ads.import_stats(
            tenant_id=tenant_id,
            platform=platform,
            account_id=account_id,
            date_from=df,
            date_to=dt,
        )

    recs = engine._reco.propose_and_cache(
        tenant_id=tenant_id,
        platform=platform,
        account_id=account_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        issuer_id=issuer_id,
    )
    stats = queue_recommendations(
        engine=engine,
        tenant_id=tenant_id,
        platform=platform,
        account_id=account_id,
        recs=recs,
        decision_id=decision_id,
        correlation_id=correlation_id,
        issuer_id=issuer_id,
    )
    return True, (
        f"queued={stats['queued']} proposed={stats['proposed']} blocked={stats['blocked']}"
    ), stats
