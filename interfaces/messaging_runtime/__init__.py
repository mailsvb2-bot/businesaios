from __future__ import annotations

CANON_MESSAGING_RUNTIME = True

__all__ = [
    "CANON_MESSAGING_RUNTIME",
    "MultichannelRuntimeApp",
    "build_multichannel_runtime_app",
]


def __getattr__(name: str):
    if name in {"MultichannelRuntimeApp", "build_multichannel_runtime_app"}:
        from interfaces.messaging_runtime.bootstrap import (
            MultichannelRuntimeApp,
            build_multichannel_runtime_app,
        )

        exports = {
            "MultichannelRuntimeApp": MultichannelRuntimeApp,
            "build_multichannel_runtime_app": build_multichannel_runtime_app,
        }
        return exports[name]
    raise AttributeError(name)
