from __future__ import annotations

from execution.effectors.ads.launch_campaign import LaunchCampaignEffector
from execution.effectors.ads.update_budget import UpdateBudgetEffector
from execution.effectors.base import EffectorBase
from execution.effectors.marketplace.route_lead import RouteLeadEffector
from execution.effectors.platforms.create_listing import CreateListingEffector
from execution.effectors.platforms.reply_to_inquiry import ReplyToInquiryEffector
from execution.effectors.platforms.request_review import RequestReviewEffector
from execution.effectors.seo.create_landing_page import CreateLandingPageEffector
from execution.effectors.seo.publish_service_page import PublishServicePageEffector
from execution.market_intelligence_effector_catalog import (
    MARKET_INTELLIGENCE_ACTION_TYPES,
    build_market_intelligence_effector,
)


CANON_EFFECTOR_CATALOG = True


_EFFECTOR_TYPES: dict[str, type[EffectorBase]] = {
    "launch_campaign": LaunchCampaignEffector,
    "update_budget": UpdateBudgetEffector,
    "create_listing": CreateListingEffector,
    "reply_to_inquiry": ReplyToInquiryEffector,
    "request_review": RequestReviewEffector,
    "route_lead": RouteLeadEffector,
    "create_landing_page": CreateLandingPageEffector,
    "publish_service_page": PublishServicePageEffector,
}


def build_effector(action_type: str) -> EffectorBase:
    normalized = str(action_type or "").strip()
    if normalized in MARKET_INTELLIGENCE_ACTION_TYPES:
        return build_market_intelligence_effector(action_type=normalized)
    effector_type = _EFFECTOR_TYPES.get(normalized)
    if effector_type is None:
        raise KeyError(f"unknown effector action_type: {normalized}")
    return effector_type()


__all__ = ["CANON_EFFECTOR_CATALOG", "build_effector"]
