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
    "application/business_autonomy/operationalization.py",
    "runtime/business_autonomy/public_api.py",
)


def test_business_autonomy_operationalization_contains_no_domain_logic() -> None:
    for target in TARGETS:
        text = Path(target).read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in text, f"{target} leaked domain logic: {pattern}"
