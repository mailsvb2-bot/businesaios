from runtime.messaging_capability import ChannelHealth, ChannelHealthRegistry, MessagingCapabilityRouter, parse_capability_requirement


def test_capability_router_filters_by_required_capabilities_preserving_order():
    router = MessagingCapabilityRouter()
    requirement = parse_capability_requirement({"subject_line": True})
    out = router.route(ordered_channels=("telegram", "email", "sms"), requirement=requirement)
    assert out.ordered_channels == ("email",)
    assert "capability_filtered" in out.reason_codes


def test_capability_router_filters_unhealthy_channels():
    registry = ChannelHealthRegistry(items=(
        ChannelHealth(channel="telegram", healthy=False, health_score=0.0, reason="down"),
        ChannelHealth(channel="email", healthy=True, health_score=1.0),
    ))
    router = MessagingCapabilityRouter(health_registry=registry)
    requirement = parse_capability_requirement({"plain_text": True})
    out = router.route(ordered_channels=("telegram", "email"), requirement=requirement)
    assert out.ordered_channels == ("email",)
    assert "health_filtered" in out.reason_codes
