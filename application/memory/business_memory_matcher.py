from __future__ import annotations

from dataclasses import dataclass

from application.memory.business_operating_memory_types import BusinessMemoryRunRecord, BusinessOperatingMemoryLike

CANON_BUSINESS_MEMORY_MATCHER = True

def _text(value: object) -> str:
    return str(value or "").strip()

def _norm(value: object) -> str:
    return _text(value).casefold().replace("-", "_").replace(" ", "_")

@dataclass(frozen=True)
class MemoryRunFingerprint:
    goal_family: str
    channel: str
    region: str
    segment: str
    offer_type: str
    traffic_source: str
    def to_dict(self) -> dict[str, str]:
        return {"goal_family": self.goal_family, "channel": self.channel, "region": self.region, "segment": self.segment, "offer_type": self.offer_type, "traffic_source": self.traffic_source}

@dataclass(frozen=True)
class SimilarRunMatch:
    run_id: str
    score: float
    goal: str
    summary: str
    channel: str
    region: str
    recorded_at: str | None

@dataclass(frozen=True)
class BusinessMemoryMatcher:
    top_k: int = 5
    def build_fingerprint(self, *, goal: str, profile: dict[str, object], meta: dict[str, object], channel: str, region: str) -> MemoryRunFingerprint:
        return MemoryRunFingerprint(goal_family=self.goal_family(goal), channel=_norm(channel), region=_norm(region), segment=_norm(dict(profile or {}).get("segment")), offer_type=_norm(dict(profile or {}).get("offer_type")), traffic_source=_norm(dict(profile or {}).get("traffic_source") or dict(meta or {}).get("traffic_source")))
    def select_similar_runs(self, *, memory: BusinessOperatingMemoryLike, target: MemoryRunFingerprint) -> tuple[SimilarRunMatch, ...]:
        ranked=[]
        for run in memory.recent_runs:
            candidate=self._run_fingerprint(run=run)
            score=self._score(target=target, candidate=candidate)
            if score<=0: continue
            ranked.append(SimilarRunMatch(run_id=run.run_id, score=score, goal=run.goal, summary=run.summary, channel=run.channel, region=run.region, recorded_at=run.recorded_at))
        ranked.sort(key=lambda item: (-float(item.score), item.run_id))
        return tuple(ranked[: int(self.top_k)])
    def _run_fingerprint(self, *, run: BusinessMemoryRunRecord) -> MemoryRunFingerprint:
        payload = dict(run.fingerprint or {})
        return MemoryRunFingerprint(goal_family=_norm(payload.get("goal_family") or run.goal_family or self.goal_family(run.goal)), channel=_norm(payload.get("channel") or run.channel), region=_norm(payload.get("region") or run.region), segment=_norm(payload.get("segment")), offer_type=_norm(payload.get("offer_type")), traffic_source=_norm(payload.get("traffic_source")))
    def _score(self, *, target: MemoryRunFingerprint, candidate: MemoryRunFingerprint) -> float:
        score=0.0
        if target.goal_family and target.goal_family == candidate.goal_family: score+=0.40
        if target.channel and target.channel == candidate.channel: score+=0.20
        if target.region and target.region == candidate.region: score+=0.10
        if target.segment and target.segment == candidate.segment: score+=0.10
        if target.offer_type and target.offer_type == candidate.offer_type: score+=0.10
        if target.traffic_source and target.traffic_source == candidate.traffic_source: score+=0.10
        return float(score)
    def goal_family(self, goal: str) -> str:
        text=_norm(goal)
        if any(token in text for token in ("acquire","lead","funnel","traffic","client")): return "acquisition"
        if any(token in text for token in ("retain","churn","repeat","loyal")): return "retention"
        if any(token in text for token in ("monet","revenue","price","ltv","cac")): return "monetization"
        if any(token in text for token in ("ops","stabil","latency","quality","execute")): return "operations"
        return "general"
__all__ = ["BusinessMemoryMatcher", "CANON_BUSINESS_MEMORY_MATCHER", "MemoryRunFingerprint", "SimilarRunMatch"]
