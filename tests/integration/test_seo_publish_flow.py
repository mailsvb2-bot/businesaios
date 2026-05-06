from growth.landing.landing_publish_service import LandingPublishService


def test_landing_publish_is_request_builder_only():
    result = LandingPublishService().publish({'page_id': 'p1'})
    assert result['kind'] == 'publish_request'
