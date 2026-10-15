from __future__ import annotations

from types import SimpleNamespace

from bootstrap.ads_wiring import AdsRuntime, build_ads_metrics_ingress


def test_ads_runtime_surface_remains_narrow_while_metrics_ingress_is_separate() -> None:
    read = SimpleNamespace(fetch_metrics=object())
    write_gateway = object()
    event_store = object()

    runtime = AdsRuntime(read=read, write_gateway=write_gateway)
    ingress = build_ads_metrics_ingress(ads_runtime=runtime, event_store=event_store)

    assert set(AdsRuntime.__dataclass_fields__) == {"read", "write_gateway"}
    assert ingress.read_service is read
    assert ingress.event_store is event_store
    assert not hasattr(runtime, "metrics_ingress")
