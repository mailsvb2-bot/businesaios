from types import SimpleNamespace

import pytest

from core.policies.telegram.routes.command_routes import status_text


@pytest.mark.parametrize(("status","access","expected"), [
 ("none",False,"платежей пока нет"), ("pending",False,"ожидает подтверждения"),
 ("succeeded",True,"Доступ: ✅ активирован"), ("failed",False,"не прошла")
])
def test_status_is_product_scoped(status,access,expected):
    ctx=SimpleNamespace(
        state=SimpleNamespace(product={"product_id":"prod-a"}),
        pay_status=status,full_access=access,
        selected_tariff={"title":"Plan"})
    assert expected in status_text(ctx)

def test_unscoped_status_never_reports_paid():
    ctx=SimpleNamespace(
        state=SimpleNamespace(product={}),pay_status="succeeded",
        full_access=True,selected_tariff={})
    assert "не привязан" in status_text(ctx)
