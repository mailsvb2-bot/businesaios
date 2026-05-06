from interfaces.web.public_site.landing_manifest import PUBLIC_SITE_MANIFEST


def test_public_site_is_canonical_surface():
    assert PUBLIC_SITE_MANIFEST['surface'] == 'interfaces.web.public_site'
    assert PUBLIC_SITE_MANIFEST['owner'] == 'application.public_site'
    assert PUBLIC_SITE_MANIFEST['capability_source_of_truth'] == 'application.business_autonomy.integration_capability_catalog'


def test_public_site_forbids_second_capability_catalog():
    assert PUBLIC_SITE_MANIFEST['must_not_hardcode_capability_truth'] is True
    assert PUBLIC_SITE_MANIFEST['must_not_publish_roadmap_as_connectable'] is True
