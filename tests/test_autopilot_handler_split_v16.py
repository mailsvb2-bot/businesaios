from pathlib import Path


def test_autopilot_handler_split_exists() -> None:
    base = Path(__file__).resolve().parents[1] / "core" / "policies" / "telegram" / "handlers" / "autopilot_parts"
    assert (base / "shared.py").exists()
    assert (base / "menu_and_dashboards.py").exists()
    assert (base / "flow.py").exists()


def test_autopilot_handler_is_thin_dispatcher() -> None:
    path = Path(__file__).resolve().parents[1] / "core" / "policies" / "telegram" / "handlers" / "autopilot.py"
    src = path.read_text(encoding="utf-8")
    assert "handle_menu_or_dashboard" in src
    assert "handle_flow" in src
    assert src.count("build_stop_loss_plan") == 0
