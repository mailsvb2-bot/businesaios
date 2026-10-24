from types import SimpleNamespace as NS

from application.business_flows import capability_parity as cp

A = cp.Availability


def test_availability_matrix():
    f = cp.availability
    assert f(statuses=("active",), runtime_enabled=False, runtime_ready=True, setup=True) == A.CONNECTED_UNAVAILABLE
    assert f(statuses=("active",), runtime_enabled=True, runtime_ready=False, setup=True) == A.ATTENTION
    assert f(statuses=("active",), runtime_enabled=True, runtime_ready=True, setup=False) == A.ACTIVE
    assert f(statuses=("attention",), runtime_enabled=True, runtime_ready=True, setup=True) == A.ATTENTION
    assert f(statuses=("pending",), runtime_enabled=True, runtime_ready=True, setup=True) == A.CONFIGURING
    assert f(statuses=("pending",), runtime_enabled=False, runtime_ready=True, setup=True) == A.CONNECTED_UNAVAILABLE
    assert f(statuses=(), runtime_enabled=True, runtime_ready=True, setup=True) == A.CONNECTABLE
    assert f(statuses=(), runtime_enabled=True, runtime_ready=True, setup=False) == A.UNAVAILABLE


def test_env_flags_and_preflight():
    env = {"CLIENTPLATFORM_OMNICHANNEL_INGRESS_ENABLED": "yes"}
    assert cp.native_runtime_state(env, lambda: NS(omnichannel_enabled=True, omnichannel_ready=True)) == (True, True)
    assert cp.native_runtime_state({**env, "CLIENTPLATFORM_DISPATCH_RUNTIME_ENABLED": "0"}, lambda: None) == (False, False)

    def boom():
        raise RuntimeError
    assert cp.native_runtime_state(env, boom) == (True, False)
    assert cp.setup_available(env, "https://x") and not cp.setup_available(env, "http://x")
    assert not cp.setup_available({}, "https://x")


def test_projection():
    caps = cp.business_capabilities(
        [("telegram", "active"), NS(platform=NS(value="VK"), status="pending"), ("whatsapp", "active")],
        setup=True, enabled={"telegram": True, "vk": True, "max": True}, ready={"telegram": True, "max": True},
        ad_statuses=("active",), ad_runtime_enabled=False)
    assert caps.messenger("telegram").active and caps.messenger("telegram").availability == A.ACTIVE
    assert caps.messenger("vk").availability == A.CONNECTED_UNAVAILABLE
    assert caps.messenger("max").can_connect
    assert caps.yandex_direct.availability == A.CONNECTED_UNAVAILABLE
    assert cp.project_yandex(None, runtime_enabled=True) is None
    assert cp.project_yandex((), runtime_enabled=True).availability == A.CONNECTABLE
