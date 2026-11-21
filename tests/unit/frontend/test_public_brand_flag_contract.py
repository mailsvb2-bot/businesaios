"""P2-50: public branding stays separate from canonical internal owner identities."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "frontend" / "src"
FLAG = 'import.meta.env.VITE_BAI_PUBLIC_BRAND_CLIENTPLATFORM === "true" ? "ClientPlatform" : "BusinessAIOS"'


def test_public_brand_exposed_by_all_owner_surfaces():
    names = ("App", "AcquisitionPlanner", "BusinessDiscoveryPanel", "BusinessIntelligencePanel",
             "CommercialSalesWorkspace", "DiscoverBuildMeasurePanel", "EventLandingWorkspace",
             "ProgramPublicationWorkspace", "PublicEventLanding", "SupportCasesWorkspace",
             "SupportOperatorConsole")
    for name in names:
        source = (ROOT / (name + ".jsx")).read_text(encoding="utf-8")
        assert FLAG in source, name


def test_brand_mark_and_browser_tab_use_same_flag():
    app = (ROOT / "App.jsx").read_text(encoding="utf-8")
    assert app.count('<span className="brand-mark">{PUBLIC_BRAND[0]}</span>') == 3
    assert 'document.title = "ClientPlatform"' in (ROOT / "main.jsx").read_text(encoding="utf-8")
    assert "ClientPlatform" in (Path(__file__).resolve().parents[3] / "core" / "ux" / "unified_messenger_menu.py").read_text(encoding="utf-8")
