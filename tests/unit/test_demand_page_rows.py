from app.web.pages.demand.business_quality import load as load_quality
from app.web.pages.demand.incoming_demand import load as load_incoming
from app.web.pages.demand.routing_decisions import load as load_routing


def test_demand_page_loaders_return_copied_rows():
    row = {'a': 1}
    rows = (row,)
    loaded = load_incoming(rows)
    assert load_quality(rows) == loaded == load_routing(rows)
    assert loaded[0] == row
    assert loaded[0] is not row
