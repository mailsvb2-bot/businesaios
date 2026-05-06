from __future__ import annotations

from core.ads.ads_service import AdsCommand, AdsPlan

from .contracts import AdsRLOptSpec, AdsRLSuggestion


def to_ads_plan(*, spec: AdsRLOptSpec, suggestion: AdsRLSuggestion) -> AdsPlan:
    payload = {
        "campaign_id": str(spec.campaign_id),
        "set": {
            key: value
            for key, value in suggestion.action.to_json().items()
            if key != "campaign_id" and value is not None
        },
        "meta": {
            "policy_id": str(suggestion.policy_id),
            "canary": bool(suggestion.canary),
            "confidence": float(suggestion.confidence),
            "reason": str(suggestion.reason),
        },
    }
    command = AdsCommand(platform=str(spec.platform), action="update_campaign", payload=payload)
    notes = (
        f"RL suggestion ({suggestion.policy_id}): {suggestion.reason}; "
        f"apply={suggestion.allow_apply} ({suggestion.safety_reason})"
    )
    return AdsPlan(commands=[command], notes=notes)
