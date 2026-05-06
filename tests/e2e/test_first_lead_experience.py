from product.magic_moment.first_lead_detector import FirstLeadDetector
from product.magic_moment.magic_moment_publisher import MagicMomentPublisher


def test_first_lead_experience_generates_magic_moment_payload():
    detected = FirstLeadDetector().detect({'lead_count': 1, 'business_id': 'b1'})
    published = MagicMomentPublisher().publish(detected)
    assert detected['kind'] == 'magic_moment'
    assert published['kind'] == 'magic_moment_event'


def test_first_lead_experience_preserves_business_id_in_published_event():
    detected = FirstLeadDetector().detect({'lead_count': 1, 'business_id': 'b1'})
    published = MagicMomentPublisher().publish(detected)
    assert published['payload']['code'] == 'magic_moment'
    assert published['payload']['business_id'] == 'b1'
