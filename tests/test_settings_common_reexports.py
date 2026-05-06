from interfaces.web.common.http_response import HttpResponse
from interfaces.web.settings.common.http_payload_reader import read_payload
from interfaces.web.settings.common.tenant_reader import read_tenant_id


def test_settings_common_owner_surfaces_are_shared_across_settings_flows() -> None:
    assert read_payload({"x": 1}) == {"x": 1}
    assert read_tenant_id(" tenant ") == "tenant"
    response = HttpResponse(status_code=200, body="ok", content_type="text/plain")
    assert response.status_code == 200
    assert response.body == "ok"
    assert response.content_type == "text/plain"
