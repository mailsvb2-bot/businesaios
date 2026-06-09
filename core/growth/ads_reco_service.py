from __future__ import annotations

from typing import Any

from core.growth.ads_config_fingerprint import ads_config_fingerprint
from core.growth.ads_reco_cache import AdsRecommendationCache
from core.growth.recommendations import AdsRecommendation


class AdsRecoService:
    def __init__(self, *, engine: Any, cache: AdsRecommendationCache, entitlements_provider: Any):
        self._engine = engine
        self._cache = cache
        self._ent = entitlements_provider

    def propose_and_cache(self, *, tenant_id: str, user_id: str | None, platform: str, account_id: str) -> list[AdsRecommendation]:
        ent = self._ent.get_ads_entitlements(tenant_id)
        lim = self._ent.get_daily_limits(tenant_id)
        fp = ads_config_fingerprint(ads_entitlements=ent, daily_limits=lim)
        recs = self._engine.propose(tenant_id=tenant_id, platform=platform, account_id=account_id)
        for r in recs:
            self._cache.put(tenant_id=tenant_id, user_id=user_id, rec_id=r.rec_id, rec_payload=_serialize(r), config_fp=fp)
        return recs

def _serialize(r: AdsRecommendation) -> dict:
    return {
        "rec_id": r.rec_id,
        "title": r.title,
        "rationale": r.rationale,
        "target": {
            "platform": r.target.platform,
            "account_id": r.target.account_id,
            "object_type": r.target.object_type,
            "object_id": r.target.object_id,
        },
        "patch": r.patch,
        "expected_impact": r.expected_impact,
        "risk_notes": r.risk_notes,
    }
