import uuid

import pytest

from application.business_flows import public_business_entry as pbe
from application.business_flows.customer_menu import uuid_token

BID = str(uuid.UUID(int=7))


def _crm():
    store: dict[tuple[str, str], str] = {}

    def find(ch, s):
        return store.get((ch, s))

    def ensure(*, channel, external_subject, display_name, customer_id):
        cid = customer_id or f"c{len(store) + 1}"
        store.setdefault((channel, external_subject), cid)
        return store[(channel, external_subject)]
    return store, find, ensure


def _cap(payloads, crm, **kw):
    store, find, ensure = crm
    args = {"business_token": uuid_token(BID), "display_name": " Анна ", "email": "A@X.ru",
            "phone": "+7 (900) 111-22-33", "business_active": lambda b: b == BID,
            "find_customer": find, "ensure_customer": ensure}
    args.update(kw)
    return pbe.capture_lead(payloads, **args)


def test_capture_creates_one_customer_and_replay_safe_fact():
    crm = _crm()
    rec, fact = _cap([], crm)
    assert rec == {"business_id": BID, "customer_id": "c1"}
    assert crm[0] == {("email", "a@x.ru"): "c1", ("phone", "79001112233"): "c1"}
    assert fact["dedupe_key"] == "website-form-submit:email:a@x.ru" and fact["source"] == "website"
    assert _cap([fact], crm)[1] is None


def test_validation_and_conflicts():
    crm = _crm()
    crm[0].update({("email", "a@x.ru"): "c1", ("phone", "79001112233"): "c2"})
    with pytest.raises(ValueError, match="different customers"):
        _cap([], crm)
    with pytest.raises(ValueError, match="email or phone"):
        _cap([], _crm(), email=None, phone="")
    with pytest.raises(ValueError, match="unavailable"):
        _cap([], _crm(), business_active=lambda b: False)
    with pytest.raises(ValueError, match="invalid"):
        _cap([], _crm(), business_token="!!")
    with pytest.raises(ValueError, match="HTTPS"):
        pbe.entry_url(public_base_url="http://x", business_id=BID)
    assert pbe.entry_url(public_base_url="https://a.ru/", business_id=BID).endswith(uuid_token(BID))
