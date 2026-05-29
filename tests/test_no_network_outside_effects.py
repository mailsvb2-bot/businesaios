from pathlib import Path

# The ONLY place real integrations are allowed:
# NOTE: transport clients may be split into runtime/_internal/effects_clients/*
ALLOWED_FILES = {
    "runtime/_internal/_effects_impl.py",
    "runtime/_internal/http_transport.py",
    "runtime/_internal/effect_payloads.py",
    "runtime/_internal/effect_router.py",
    "runtime/_internal/effect_types.py",
    # Non-executing provider metadata and token-resolution surfaces are allowed
    # to mention external endpoints/env keys; transport execution remains sealed.
    "runtime/business_autonomy/provider_transport_bindings.py",
    "runtime/boot/telegram_webhook_runner.py",
}

ALLOWED_PREFIXES = ("runtime/_internal/effects_clients/", "runtime/_internal/effects_actions/", "canon/domain_fs/",)
MARKERS = [
    "api.telegram.org",
    "api.yookassa.ru",
    "YOOKASSA",
    "TELEGRAM_BOT_TOKEN",
    "import requests",
    "from requests",
    "import httpx",
    "from httpx",
    "urllib.request",
    "urllib3.",
    "socket.socket",
    "aiohttp.",
]


def test_no_network_markers_outside_sealed_effects():
    root = Path(__file__).resolve().parents[1]
    bad = []
    for py in root.rglob("*.py"):
        rel = py.relative_to(root).as_posix()
        if rel in ALLOWED_FILES or rel.startswith(ALLOWED_PREFIXES):
            continue
        if rel.startswith(("tests/", "scripts/")):
            continue
        txt = py.read_text(encoding="utf-8", errors="ignore")
        for m in MARKERS:
            if m in txt:
                bad.append(f"{rel} -> {m}")
                break
    if bad:
        raise AssertionError("Network/integration markers found outside sealed effects:\n" + "\n".join(sorted(bad)))
