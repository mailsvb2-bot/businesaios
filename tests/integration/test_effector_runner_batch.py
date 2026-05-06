from __future__ import annotations

from execution.runners.marketplace.route_lead import Runner as RouteLeadRunner
from execution.runners.platforms.reply_to_inquiry import Runner as ReplyToInquiryRunner
from execution.runners.seo.publish_service_page import Runner as PublishServicePageRunner


def test_marketplace_runner_is_fail_closed_until_real_routing_connector_exists() -> None:
    runner = RouteLeadRunner()
    result = runner.run(
        {
            "action_id": "lead-1",
            "channel": "marketplace",
            "decision_id": "dec-1",
            "correlation_id": "corr-1",
            "payload": {"lead_id": "lead-1", "target_business_id": "biz-7"},
        }
    )
    assert result.status == "operator_required"
    assert result.payload["effector"]["verified"] is False
    assert result.payload["external_system"] == "marketplace"


def test_external_connector_backed_runners_fail_closed_with_operator_signal() -> None:
    reply = ReplyToInquiryRunner().run(
        {
            "action_id": "inq-1",
            "channel": "platforms",
            "decision_id": "dec-2",
            "correlation_id": "corr-2",
            "payload": {"listing_id": "l-1", "message": "hello"},
        }
    )
    page = PublishServicePageRunner().run(
        {
            "action_id": "page-1",
            "channel": "seo",
            "decision_id": "dec-3",
            "correlation_id": "corr-3",
            "payload": {"slug": "window-cleaning"},
        }
    )
    assert reply.status == "operator_required"
    assert page.status == "operator_required"
    assert reply.payload["effector"]["retry_kind"] == "operator_required"
    assert page.payload["effector"]["code"] == "not_configured"
