from growth.core.growth_engine import GrowthEngine
from growth.engine_contract import (
    BUDGET_ENGINE_PACKAGE_KIND,
    CAMPAIGN_ENGINE_PACKAGE_KIND,
    CREATIVE_ENGINE_PACKAGE_KIND,
    GROWTH_PLAN_KIND,
    PLATFORM_ENGINE_PACKAGE_KIND,
    SEO_ENGINE_PACKAGE_KIND,
    build_artifact,
    build_package,
)


def test_growth_engine_contract_helpers_build_canonical_shapes() -> None:
    payload = {"channel": "ads"}
    artifact = build_artifact("audience", payload)
    package = build_package("sample_package", payload, audience=artifact)

    assert artifact == {"kind": "audience", "payload": payload}
    assert package == {"kind": "sample_package", "payload": payload, "audience": artifact}


def test_growth_engine_package_kind_constants_are_stable() -> None:
    assert GROWTH_PLAN_KIND == "growth_plan"
    assert CAMPAIGN_ENGINE_PACKAGE_KIND == "campaign_engine_package"
    assert CREATIVE_ENGINE_PACKAGE_KIND == "creative_engine_package"
    assert BUDGET_ENGINE_PACKAGE_KIND == "budget_engine_package"
    assert SEO_ENGINE_PACKAGE_KIND == "seo_engine_package"
    assert PLATFORM_ENGINE_PACKAGE_KIND == "platform_engine_package"


def test_growth_engine_emits_observability_events_without_changing_contract() -> None:
    class _EventLog:
        def __init__(self) -> None:
            self.events = []

        def emit(self, **payload) -> None:
            self.events.append(dict(payload))

    event_log = _EventLog()
    engine = GrowthEngine(event_log=event_log)

    plan = engine.assemble_growth_plan({"channel": "ads"})
    candidates = engine.assemble_opportunities([{"channel": "ads", "score": 0.9}])

    assert plan["kind"] == GROWTH_PLAN_KIND
    assert candidates[0].channel == "ads"
    assert [item["event_type"] for item in event_log.events] == ["growth", "growth"]
    assert [item["payload"]["name"] for item in event_log.events] == [
        "growth_plan_assembled",
        "growth_opportunities_assembled",
    ]
