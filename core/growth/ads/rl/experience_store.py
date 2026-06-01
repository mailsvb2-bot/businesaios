from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from core.events.log import EventLog

from .contextual_bandit_policy import ArmStat, action_key
from .contracts import AdsRLAction, AdsRLState, AdsRLSuggestion
from .reward import RewardBreakdown

Json = dict[str, Any]


@dataclass(frozen=True)
class RLStep:
    ts_ms: int
    policy_id: str
    campaign_id: str
    platform: str
    action_key: str
    action: Json
    reward: float | None = None
    reward_mode: str | None = None
    meta: Json = None  # type: ignore[assignment]


class AdsRLExperienceStore:
    """Append-only experience store backed by the canonical EventStore.

    Events:
      - ads_rl_suggested@v1
      - ads_rl_observed@v1  (reward attached)
    """

    def __init__(self, event_store: Any, *, source: str = "ads_rl") -> None:
        self._es = event_store
        self._source = str(source or "ads_rl")

    def _log(self, *, tenant_id: str) -> EventLog:
        # Tenant-scoped EventLog is the only allowed write-path.
        return EventLog(self._es, tenant=str(tenant_id))

    def append_suggested(
        self, *, tenant_id: str, user_id: str | None, suggestion: AdsRLSuggestion, state: AdsRLState, meta: Json
    ) -> None:
        now = int(time.time() * 1000)
        ak = action_key(suggestion.action)
        ev = {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id or ""),
            "source": self._source,
            "event_type": "ads_rl_suggested@v1",
            "timestamp_ms": int(now),
            "payload": {
                "policy_id": str(suggestion.policy_id),
                "campaign_id": str(state.campaign_id),
                "platform": str(state.platform),
                "action_key": str(ak),
                "action": dict(suggestion.action.to_json()),
                "confidence": float(suggestion.confidence),
                "reason": str(suggestion.reason),
                "canary": bool(suggestion.canary),
                "allow_apply": bool(suggestion.allow_apply),
                "safety_reason": str(suggestion.safety_reason or ""),
                "state": _state_to_json(state),
                "meta": dict(meta or {}),
            },
        }
        self._log(tenant_id=str(tenant_id)).append(ev)

    def append_observed(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        policy_id: str,
        state: AdsRLState,
        action: AdsRLAction,
        reward: RewardBreakdown,
        meta: Json,
    ) -> None:
        now = int(time.time() * 1000)
        ak = action_key(action)
        ev = {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id or ""),
            "source": self._source,
            "event_type": "ads_rl_observed@v1",
            "timestamp_ms": int(now),
            "payload": {
                "policy_id": str(policy_id),
                "campaign_id": str(state.campaign_id),
                "platform": str(state.platform),
                "action_key": str(ak),
                "action": dict(action.to_json()),
                "reward": float(reward.reward),
                "reward_mode": str(reward.mode),
                "reward_components": dict(reward.components or {}),
                "state": _state_to_json(state),
                "meta": dict(meta or {}),
            },
        }
        self._log(tenant_id=str(tenant_id)).append(ev)

    def load_recent_observed(self, *, tenant_id: str, campaign_id: str, limit: int = 500) -> list[RLStep]:
        try:
            events = self._es.latest_events(tenant_id=str(tenant_id), event_types=("ads_rl_observed@v1",), limit=int(limit))
        except Exception:
            events = []

        out: list[RLStep] = []
        for e in events:
            payload = e.get("payload") or {}
            if str(payload.get("campaign_id") or "") != str(campaign_id):
                continue
            try:
                ts = int(e.get("timestamp_ms") or 0)
            except Exception:
                ts = 0
            meta = payload.get("meta") or {}
            out.append(
                RLStep(
                    ts_ms=ts,
                    policy_id=str(payload.get("policy_id") or ""),
                    campaign_id=str(payload.get("campaign_id") or ""),
                    platform=str(payload.get("platform") or ""),
                    action_key=str(payload.get("action_key") or ""),
                    action=dict(payload.get("action") or {}),
                    reward=(float(payload.get("reward")) if payload.get("reward") is not None else None),
                    reward_mode=str(payload.get("reward_mode") or ""),
                    meta=dict(meta or {}),
                )
            )
        return out

    def compute_arm_stats(self, *, tenant_id: str, campaign_id: str, limit: int = 2000) -> dict[str, ArmStat]:
        steps = self.load_recent_observed(tenant_id=str(tenant_id), campaign_id=str(campaign_id), limit=int(limit))
        stats: dict[str, ArmStat] = {}
        for s in steps:
            if s.reward is None:
                continue
            key = str(s.action_key or "")
            if not key:
                continue
            st = stats.get(key)
            if st is None:
                stats[key] = ArmStat(pulls=1, reward_sum=float(s.reward))
            else:
                stats[key] = ArmStat(pulls=int(st.pulls) + 1, reward_sum=float(st.reward_sum) + float(s.reward))
        return stats


def _state_to_json(state: AdsRLState) -> Json:
    return {
        "tenant_id": str(state.tenant_id),
        "platform": str(state.platform),
        "campaign_id": str(state.campaign_id),
        "ts_ms": int(state.ts_ms),
        "impressions": int(state.impressions),
        "clicks": int(state.clicks),
        "leads": int(state.leads),
        "purchases": int(state.purchases),
        "spend": float(state.spend),
        "revenue": float(state.revenue),
        "day_of_week": int(state.day_of_week),
        "hour_of_day": int(state.hour_of_day),
    }
