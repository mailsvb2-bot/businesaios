from runtime.boot.ads_wiring import AdsRuntime


def test_ads_runtime_surface_is_narrow():
    # AdsRuntime must not expose registries or connectors.
    fields = set(getattr(AdsRuntime, "__dataclass_fields__", {}).keys())
    assert fields == {"read", "write_gateway"}
