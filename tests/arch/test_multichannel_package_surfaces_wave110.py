from __future__ import annotations

from importlib import import_module
from pathlib import Path

PACKAGES = (
    "interfaces.messaging.email",
    "interfaces.messaging.instagram",
    "interfaces.messaging.messenger",
    "interfaces.messaging.sms",
    "interfaces.messaging.whatsapp",
    "interfaces.regional.kakaotalk",
    "interfaces.regional.line",
    "interfaces.regional.viber",
    "interfaces.regional.wechat",
    "interfaces.web.api_gateway",
)

REMOVED = (
    "adapter.py",
    "delivery_mapper.py",
    "inbound_normalizer.py",
    "outbound_sender.py",
    "runner.py",
    "runner_components.py",
    "runner_helpers.py",
    "runtime_binding.py",
)


def test_multichannel_packages_export_canonical_surfaces() -> None:
    for dotted in PACKAGES:
        module = import_module(dotted)
        for attr in (
            "Adapter",
            "Runner",
            "build_binding",
            "build_config",
            "delivery_preview",
            "map_result",
            "normalize_inbound",
            "send_raw",
            "sender_identity",
        ):
            assert hasattr(module, attr), (dotted, attr)


def test_duplicate_multichannel_surface_files_are_removed() -> None:
    for dotted in PACKAGES:
        package_dir = Path(dotted.replace(".", "/"))
        for rel in REMOVED:
            assert not (package_dir / rel).exists(), str(package_dir / rel)
