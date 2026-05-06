from pathlib import Path

FORBIDDEN_PATTERNS = (
    "resource_trance",
    "gentle_reactivation",
    "therapeutic",
    "session_kind",
    "discount_for_user",
    "copy_variant",
)


def test_business_autonomy_route_handlers_contain_no_domain_logic() -> None:
    text = Path("interfaces/api/business_autonomy_route_handlers.py").read_text(encoding="utf-8")
    for pattern in FORBIDDEN_PATTERNS:
        assert pattern not in text, f"interfaces/api/business_autonomy_route_handlers.py leaked domain logic: {pattern}"
