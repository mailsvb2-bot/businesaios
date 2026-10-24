from datetime import UTC, datetime

import pytest

from application.business_flows import customer_activity as ca

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
CUST = [
    {
        "id": "c1",
        "business_id": "b",
        "first_contact_at": "2026-10-23T09:00:00Z",
        "last_contact_at": "2026-10-23T10:00:00Z",
    },
    {
        "id": "c2",
        "business_id": "b",
        "first_contact_at": "2026-10-01T09:00:00",
        "last_contact_at": "2026-10-20T09:00:00",
    },
    {"id": "staff", "business_id": "b", "first_contact_at": "2026-10-23T09:00:00Z", "last_contact_at": ""},
    {"id": "o", "business_id": "other", "first_contact_at": "2026-10-23T09:00:00Z", "last_contact_at": ""},
]
IDS = [
    {"business_id": "b", "customer_id": "c1", "platform": "Telegram", "external_subject": "1", "username": "ann"},
    {"business_id": "b", "customer_id": "c1", "platform": "vk", "external_subject": "v1"},
    {
        "business_id": "b",
        "customer_id": "c2",
        "platform": "max",
        "external_subject": "m",
        "last_contact_at": "2026-10-23T11:00:00Z",
    },
    {"business_id": "b", "customer_id": "staff", "platform": "telegram", "external_subject": "99"},
]


def test_tenant_summary_excludes_staff_and_other_tenant():
    s = ca.tenant_activity("b", CUST, IDS, staff={"b": {"99"}}, now=NOW)
    assert s.total == 2 and s.new_today == 1 and s.new_7d == 1 and s.active_today == 2
    assert s.by_platform == {"max": 1, "telegram": 1, "vk": 1}
    assert s.recent[0].customer_id == "c2" and s.recent[0].last_contact_at == "2026-10-23T11:00:00Z"
    assert s.recent[1].username == "ann" and s.recent[1].platforms == ("telegram", "vk")


def test_platform_requires_admin_and_excludes_admin_subjects():
    with pytest.raises(PermissionError):
        ca.platform_activity(is_platform_admin=False, customers=CUST, identities=IDS, staff={})
    s = ca.platform_activity(
        is_platform_admin=True, customers=CUST, identities=IDS, staff={}, admin_subjects={"1"}, now=NOW
    )
    assert {r.customer_id for r in s.recent} == {"c2", "staff", "o"}


def test_record_contact_only_linked_identity():
    f = ca.record_customer_contact(IDS, business_id="b", platform="VK", external_subject="v1", at=NOW)
    assert f["customer_id"] == "c1" and f["at"] == "2026-10-23T12:00:00+00:00"
    assert ca.record_customer_contact(IDS, business_id="b", platform="vk", external_subject="nope") is None
    assert ca.parse_dt("bad") is None
