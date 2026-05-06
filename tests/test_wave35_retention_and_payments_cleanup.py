from core.retention.engine_support import parse_decide_offer_context


def test_retention_context_parser_respects_now_ms() -> None:
    day_key, day_index, now_ms = parse_decide_offer_context(
        {"day_key": "day:2026-03-13", "day_index": "4", "now_ms": "123456"}
    )
    assert day_key == "day:2026-03-13"
    assert day_index == 4
    assert now_ms == 123456


def test_payments_reconciliation_uses_support_module() -> None:
    text = open(
        "runtime/_internal/effects_actions/payments/reconciliation.py",
        "r",
        encoding="utf-8",
    ).read()
    assert "reconciliation_support import" in text
    assert "processed\": int(processed_any)" in text
    assert "skipped_already\": int(skipped_already)" in text
