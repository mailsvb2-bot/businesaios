from __future__ import annotations

from runtime.platform.support.integrations import (
    ExperimentTrackerAdapter,
    FeatureStoreAdapter,
    MessageBusAdapter,
    MetricsAdapter,
    ObjectStoreAdapter,
    SchedulerAdapter,
    SecretsManagerAdapter,
    SQLAdapter,
    TracingAdapter,
)


def test_platform_support_local_integrations_are_concrete_and_stateful() -> None:
    tracker = ExperimentTrackerAdapter()
    tracker.track({"experiment": "ads-rl", "variant": "b"})
    assert tracker.records() == [{"experiment": "ads-rl", "variant": "b"}]

    store = FeatureStoreAdapter()
    store.put("tenant:1", {"ctr": 0.3})
    assert store.fetch("tenant:1") == {"ctr": 0.3}
    assert store.fetch_many(["tenant:1", "tenant:2"]) == {"tenant:1": {"ctr": 0.3}}

    bus = MessageBusAdapter()
    bus.publish("policy", {"name": "strict"})
    bus.publish("policy", {"name": "safe"})
    assert bus.topics() == ("policy",)
    assert bus.messages("policy") == [{"name": "strict"}, {"name": "safe"}]

    metrics = MetricsAdapter()
    metrics.increment("jobs")
    metrics.increment("jobs", 2)
    metrics.set("latency_ms", 12)
    assert metrics.get("jobs") == 3.0
    assert metrics.snapshot()["latency_ms"] == 12.0

    objects = ObjectStoreAdapter()
    objects.put("model.bin", b"abc")
    assert objects.get("model.bin") == b"abc"
    assert objects.keys() == ("model.bin",)
    objects.delete("model.bin")
    assert objects.keys() == ()

    scheduler = SchedulerAdapter()
    scheduler.schedule("refresh", {"tenant": "a"})
    assert scheduler.jobs() == [{"job_name": "refresh", "payload": {"tenant": "a"}}]

    secrets = SecretsManagerAdapter({"token": "x"})
    secrets.set("secret", "y")
    assert secrets.get("token") == "x"
    assert secrets.require("secret") == "y"

    tracing = TracingAdapter()
    tracing.record("rollout", {"approved": True})
    assert tracing.events() == [{"name": "rollout", "payload": {"approved": True}}]


def test_platform_support_sql_adapter_executes_local_sqlite_queries() -> None:
    sql = SQLAdapter()
    assert sql.execute("create table metrics (name text, value integer)") == -1
    assert sql.execute("insert into metrics(name, value) values (?, ?)", ("ctr", 7)) == 1
    rows = sql.execute("select name, value from metrics")
    assert rows == [{"name": "ctr", "value": 7}]
