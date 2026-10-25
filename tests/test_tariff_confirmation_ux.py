from core.ai.world_state import WorldStateV1
from core.policies.telegram_policies import UnifiedTelegramPolicyV3
from core.tenancy.tenant import current_tenant_id


def _state_for_cb(cb: str) -> WorldStateV1:
    return WorldStateV1(
        schema_version=1,
        user={"settings": {}, "selected_tariff": {}},
        session={"is_callback": True, "callback_data": cb, "text": ""},
        product={},
        economy={"entitlements": {}, "payments": {}},
        timestamp_ms=0,
        tenant_id=current_tenant_id(),
        user_id="u1",
    )


def test_tariff_selection_renders_confirmation_text():
    pol = UnifiedTelegramPolicyV3()
    out = pol.propose(_state_for_cb("sub:buy:1:1990"))
    assert getattr(out, "action", None) == "send_message@v1"
    p = getattr(out, "payload", {})
    txt = str(p.get("notify_text") or "")
    assert "Утро — 5 дней" not in txt
    assert "1990" not in txt
