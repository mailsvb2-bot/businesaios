from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding


def test_messaging_providers_expose_binding_metadata():
    providers = provider_map()
    assert describe_provider_messaging_binding(providers['telegram_bot']).channel == 'telegram'
    assert describe_provider_messaging_binding(providers['whatsapp_cloud']).channel == 'whatsapp'
    assert describe_provider_messaging_binding(providers['email_connector']).required_capabilities['subject_line'] is True
    assert describe_provider_messaging_binding(providers['sms_connector']).required_capabilities['plain_text'] is True
