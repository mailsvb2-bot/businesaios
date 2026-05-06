from application.public_site.landing_content import PUBLIC_SITE_SECTION_ORDER, build_landing_payload
from application.public_site.service import PublicSiteService


def test_public_site_has_required_sections():
    payload = build_landing_payload()
    assert payload['sections_order'] == list(PUBLIC_SITE_SECTION_ORDER)
    for section in PUBLIC_SITE_SECTION_ORDER:
        assert section in payload['sections']


def test_public_site_capabilities_come_from_backend_catalog():
    payload = build_landing_payload()
    assert payload['capabilities']['source_of_truth'] == 'application.business_autonomy.integration_capability_catalog'
    assert payload['sections']['capabilities']['summary']['total'] >= 1


def test_roadmap_capabilities_are_not_connectable():
    payload = build_landing_payload()
    for item in payload['sections']['capabilities']['cards']:
        if item['roadmap_only']:
            assert item['connectable'] is False


def test_public_site_admin_status_is_safe():
    status = PublicSiteService().admin_status()
    assert status['surface'] == 'public_site'
    assert status['safe_to_publish'] is True
    assert status['violations'] == []
