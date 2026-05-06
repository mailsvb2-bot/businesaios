from __future__ import annotations

from execution.effectors import build_effector
from execution.effectors.marketplace.route_lead import RouteLeadEffector
from execution.effectors.platforms.reply_to_inquiry import ReplyToInquiryEffector


def test_catalog_builds_explicit_effector_classes() -> None:
    assert build_effector("reply_to_inquiry").__class__ is ReplyToInquiryEffector
    assert build_effector("route_lead").__class__ is RouteLeadEffector


def test_missing_route_is_fail_closed_operator_required() -> None:
    result = build_effector("route_lead").execute({"action_id": "lead-1", "payload": {}})
    assert result.attempted is True
    assert result.executed is False
    assert result.verified is False
    assert result.code == "connector_not_available"
    assert result.operator_required is True
