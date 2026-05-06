from pathlib import Path

FORBIDDEN_PATTERNS = (
    "resource_trance",
    "gentle_reactivation",
    "therapeutic",
    "session_kind",
    "discount_for_user",
    "copy_variant",
)

TARGETS = (
    "entrypoints/api/admin_route_handlers.py",
    "application/business_autonomy/policy_alignment.py",
)


def test_business_autonomy_admin_surface_contains_no_domain_logic() -> None:
    for target in TARGETS:
        text = Path(target).read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in text, f"{target} leaked domain logic: {pattern}"
