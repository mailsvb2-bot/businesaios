"""Behavior telemetry read-model (best-effort).

This is a lightweight projection over behavior_telemetry events.
It must never raise.
"""

from __future__ import annotations

import time
from typing import Any

from config.final_hidden_logic_policy import DEFAULT_BEHAVIOR_TELEMETRY_POLICY
from core.behavior.dirac_behavior import Complex4, DiracBehaviorModel
from core.behavior.org_field import OrgField, aggregate_org_observables
from core.events.read_model_support import best_effort_iter_events, best_effort_latest_events
from core.observability.silent import swallow


def behavior_snapshot(
    event_store: Any,
    *,
    tenant_id: str = DEFAULT_BEHAVIOR_TELEMETRY_POLICY.default_tenant_id,
    user_id: str,
    limit: int = DEFAULT_BEHAVIOR_TELEMETRY_POLICY.default_limit,
    lookback_days: int = DEFAULT_BEHAVIOR_TELEMETRY_POLICY.default_lookback_days,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "clicks_total": 0,
        "callbacks_total": 0,
        "messages_total": 0,
        "last_ts_ms": 0,
        "last_button_id": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.default_button_id,
        "audio_starts": 0,
        "audio_completions": 0,
        "audio_total_listen_ms": 0,
        "fast_actions_10s": 0,
        # BusinesAIOS behavioral observables (Dirac-inspired, deterministic)
        "engagement_score": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero,
        "hesitation_score": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero,
        "purchase_probability": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero,
        "fatigue_index": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero,
        "trust_index": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero,
        "coherence": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero,
        "anti": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero,
        # Optional org-level (B2B) aggregation
        "org": dict(DEFAULT_BEHAVIOR_TELEMETRY_POLICY.default_org),
    }

    try:
        now_ms = int(time.time() * DEFAULT_BEHAVIOR_TELEMETRY_POLICY.milliseconds_per_second)
        start_ms = max(0, now_ms - int(lookback_days) * DEFAULT_BEHAVIOR_TELEMETRY_POLICY.seconds_per_day * DEFAULT_BEHAVIOR_TELEMETRY_POLICY.milliseconds_per_second)
        evs = []
        # Pull a bounded, mixed window: behavior_telemetry + key funnel events.
        # Note: older stores might not support event_types arg; the canonical helper
        # chooses only supported signatures and keeps failures observable.
        wanted = list(DEFAULT_BEHAVIOR_TELEMETRY_POLICY.wanted_event_types)
        evs = best_effort_latest_events(
            event_store=event_store,
            where='core/telemetry/behavior_read_model.behavior_snapshot.latest_events',
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            event_types=tuple(wanted),
            legacy_event_type="behavior_telemetry",
            limit=int(limit),
        )
        if not evs:
            # Best-effort: only behavior_telemetry in iter mode.
            evs = best_effort_iter_events(
                event_store=event_store,
                where='core/telemetry/behavior_read_model.behavior_snapshot.iter_events',
                tenant_id=str(tenant_id),
                event_types=("behavior_telemetry",),
                start_ms=int(start_ms),
                end_ms=None,
                user_id=str(user_id),
            )
            evs = evs[-int(limit):]
        if not evs and not hasattr(event_store, 'latest_events') and not hasattr(event_store, 'iter_events'):
            return out

        # Compute in chronological order for delta and to feed behavior dynamics.
        evs_sorted = sorted([e for e in evs if isinstance(e, dict)], key=lambda e: int(e.get("timestamp_ms") or 0))
        prev_ts = None

        # --- Dirac-inspired behavior model (lead) ---
        # This enrichment is best-effort: a behavior-physics issue must not erase
        # stable counters such as messages_total/callbacks_total from the read model.
        model = DiracBehaviorModel()
        psi0 = Complex4.zeros().renormalize(target_norm=DEFAULT_BEHAVIOR_TELEMETRY_POLICY.target_norm)
        try:
            psi_final, obs = model.evolve(psi=psi0, events=evs_sorted, now_ms=int(now_ms), context={"anti": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.org_context_anti})
            out.update(
                {
                    "engagement_score": float(obs.get("engagement_score", DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero)),
                    "hesitation_score": float(obs.get("hesitation_score", DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero)),
                    "purchase_probability": float(obs.get("purchase_probability", DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero)),
                    "fatigue_index": float(obs.get("fatigue_index", DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero)),
                    "trust_index": float(obs.get("trust_index", DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero)),
                    "coherence": float(obs.get("coherence", DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero)),
                    "anti": float(obs.get("anti", DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero)),
                }
            )
        except Exception:
            swallow(__name__, "core/telemetry/behavior_read_model.behavior_snapshot.dirac")

        # --- Optional B2B org field aggregation ---
        # If events include payload.actor_role, we aggregate per-role.
        try:
            psi_by_role: dict[str, Complex4] = {}
            anti_by_role: dict[str, float] = {}
            buckets: dict[str, list[dict]] = {}
            for e in evs_sorted:
                p = e.get("payload") or {}
                if not isinstance(p, dict):
                    continue
                role = str(p.get("actor_role") or "").strip().lower()
                if not role:
                    continue
                buckets.setdefault(role, []).append(e)
            if buckets:
                for role, evr in buckets.items():
                    psi_r, obs_r = model.evolve(psi=psi0, events=evr, now_ms=int(now_ms), context={"anti": DEFAULT_BEHAVIOR_TELEMETRY_POLICY.org_context_anti})
                    psi_by_role[role] = psi_r
                    anti_by_role[role] = float(obs_r.get("anti", DEFAULT_BEHAVIOR_TELEMETRY_POLICY.engagement_zero))
                field = OrgField(psi_by_role=psi_by_role, anti_by_role=anti_by_role)
                out["org"] = aggregate_org_observables(model=model, field=field, now_ms=int(now_ms))
            else:
                out["org"] = {}
        except Exception:
            out["org"] = {}

        for e in evs_sorted:
            ts = int(e.get("timestamp_ms") or 0)
            p = e.get("payload") or {}
            if not isinstance(p, dict) or p.get("schema") != DEFAULT_BEHAVIOR_TELEMETRY_POLICY.behavior_schema:
                continue
            kind = str(p.get("kind") or "")
            button_id = str(p.get("button_id") or "")

            if kind == DEFAULT_BEHAVIOR_TELEMETRY_POLICY.callback_kind:
                out["callbacks_total"] += 1
                out["clicks_total"] += 1
            elif kind == DEFAULT_BEHAVIOR_TELEMETRY_POLICY.message_kind:
                out["messages_total"] += 1

            if button_id:
                out["last_button_id"] = button_id

            if prev_ts is not None and ts >= prev_ts:
                delta = ts - prev_ts
                if delta <= DEFAULT_BEHAVIOR_TELEMETRY_POLICY.zero_seconds_window_ms:
                    out["fast_actions_10s"] += 1
            prev_ts = ts

            # audio
            if p.get("audio_id"):
                out["audio_starts"] += 1
                pos = p.get("audio_pos_ms")
                if isinstance(pos, int) and pos >= 0:
                    out["audio_total_listen_ms"] += int(pos)
                if p.get("audio_completed") is True:
                    out["audio_completions"] += 1

            out["last_ts_ms"] = max(int(out["last_ts_ms"]), ts)

        return out
    except Exception:
        return out
