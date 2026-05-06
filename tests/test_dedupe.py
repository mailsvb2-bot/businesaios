from core.marketing.dedupe import DedupeConfig, MessageDedupe


def test_dedupe_blocks_repeat():
    d = MessageDedupe(DedupeConfig(cooldown_s=60))
    assert d.allow(tenant_id="t", user_id="u", text="hi")
    assert not d.allow(tenant_id="t", user_id="u", text="hi")
    assert d.allow(tenant_id="t", user_id="u", text="hi2")
