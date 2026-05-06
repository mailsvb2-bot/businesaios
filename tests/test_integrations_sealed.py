from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALLOWED_FILES = {"runtime/_internal/_effects_impl.py"}
ALLOWED_PREFIXES = ("runtime/_internal/effects_clients/", "runtime/_internal/effects_actions/",)
MARKERS = [
    "api.yookassa.ru",
    "api.telegram.org",
    "TELEGRAM_BOT_TOKEN",
    "YOOKASSA_SECRET_KEY",
]


def test_real_integrations_only_in_private_effects_impl():
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        txt = py.read_text(encoding="utf-8", errors="ignore")
        if any(m in txt for m in MARKERS):
            assert (rel in ALLOWED_FILES) or rel.startswith(ALLOWED_PREFIXES), (
                f"Integration marker found in {rel}; allowed only in {sorted(ALLOWED_FILES)} or under {ALLOWED_PREFIXES}"
            )


def test_no_infra_payments_module():
    # User requirement: real integrations only inside runtime/_internal/_effects_impl.py.
    assert not (ROOT / "infra" / "payments").exists(), (
        "infrastructure/payments must not exist; keep integrations sealed in runtime/_internal/_effects_impl.py"
    )
