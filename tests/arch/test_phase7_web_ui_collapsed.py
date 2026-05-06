from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGES = PROJECT_ROOT / "app" / "web" / "pages"


def test_only_dashboard_and_autopilot_page_wrappers_remain() -> None:
    py_files = sorted(p.name for p in PAGES.glob("*.py"))
    assert py_files == ["__init__.py", "autopilot.py", "dashboard.py"]


def test_demand_pages_live_in_separate_subpackage() -> None:
    demand = PAGES / "demand"
    assert demand.exists()
    assert (demand / "__init__.py").exists()
