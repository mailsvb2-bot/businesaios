from pathlib import Path


def test_runtime_web_modules_avoid_retired_public_api_leaf_modules() -> None:
    expected = {
        Path("runtime/boot/web/runtime_web_service_builders.py"): [
            "from runtime.boot.web.messaging_policy_alert_subscription_service import",
            "from runtime.boot.web.messaging_policy_service_graph import",
        ],
        Path("runtime/boot/web/messaging_policy_dashboard_boot.py"): [
            "from runtime.boot.web.messaging_policy_service_graph import",
        ],
        Path("runtime/boot/web/fastapi_components/__init__.py"): [
            "from interfaces.web.debug.messaging_policy_alerts.fastapi_adapter import",
            "from runtime.boot.web.messaging_policy_service_graph import",
        ],
        Path("runtime/boot/web/flask_components/__init__.py"): [
            "from interfaces.web.debug.messaging_policy_alerts.flask_adapter import",
            "from runtime.boot.web.messaging_policy_service_graph import",
        ],
    }
    forbidden = (
        "from runtime.boot.web.public_api_bundles import",
        "from runtime.boot.web.public_api_graphs import",
        "from runtime.boot.web.public_api_observability import",
        "from runtime.boot.web.public_api_runtime import",
        "from runtime.boot.web.public_api_settings import",
    )
    for path, markers in expected.items():
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, f"expected {marker!r} in {path}"
        for marker in forbidden:
            assert marker not in text, f"did not expect {marker!r} in {path}"
