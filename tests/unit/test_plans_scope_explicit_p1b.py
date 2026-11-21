"""P1b: no plan or pricing advice is selected from process-wide environment scope."""
from core.plans import catalog
from core.policies.telegram.helpers import build_legacy_prices
from interfaces.telegram.read_models.components import pricing


def test_process_environment_cannot_select_catalog(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "_repo_root", lambda: tmp_path)
    path = tmp_path / "data" / "plan_catalogs" / "tenant" / "product.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"tenant_id":"tenant","product_id":"product","plans":[{"plan_id":2,"title":"Workspace","price":2490,"days":30,"scope":"monthly","plan_code":"w"}]}')
    monkeypatch.setenv("TENANT_ID", "tenant")
    monkeypatch.setenv("PRODUCT_ID", "product")
    assert catalog.active_plans() == []
    assert catalog.plan_by_id(2, tenant_id="tenant", product_id="product") is not None
    assert build_legacy_prices(default_price_rub=4900) == {"Полный доступ": 4900}
    assert build_legacy_prices(default_price_rub=4900, tenant_id="tenant", product_id="product") == {"Workspace": 2490}


def test_unscoped_autopricing_never_reads_plan_catalog(monkeypatch):
    monkeypatch.setattr(pricing.FeatureFlags, "AUTOPRICING", True, raising=False)
    monkeypatch.setattr(catalog, "active_plans", lambda **kw: (_ for _ in ()).throw(AssertionError("unscoped catalog read")))
    assert pricing.load_pricing_suggestions(object(), tenant_id="tenant") == {}
