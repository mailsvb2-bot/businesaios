from growth.platforms.listing_content_builder import ListingContentBuilder


def test_listing_content_builder_returns_payload():
    result = ListingContentBuilder().build({'listing_id': 'x'})
    assert result['kind'] == 'listing_content'
