from core.policies.product_domains.sales_domain import SalesDomainPolicyV1


class _State:
    def __init__(self):
        self.session = {
            "text": "",
            "is_callback": True,
            "callback_data": "sales:one_click_value",
            "callback_query_id": "cq1",
        }
        self.user_id = "u1"
        self.tenant_id = "t1"
        self.user = {"locale": "ru", "behavioral_state": {"segment": "warm"}}
        self.product = {}
        self.marketing_seed = "1"


def test_sales_domain_one_click_value_proposes_action():
    pol = SalesDomainPolicyV1()
    a = pol.propose(_State())
    assert a.action == "one_click_value@v1"
    assert a.payload.get("track_event_type") == "one_click_value_shown"
    tp = a.payload.get("track_payload") or {}
    assert tp.get("step_key") == "sales:one_click_value"
