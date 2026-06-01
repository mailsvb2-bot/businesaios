from interfaces.web.debug.messaging_policy_observability_nav.page_presenter import present_page


def test_present_page_builds_links_with_tenant():
    model = present_page(tenant_id="t1")
    assert model.tenant_id == "t1"
    assert len(model.items) >= 5
    assert "tenant_id=t1" in model.items[0].href
