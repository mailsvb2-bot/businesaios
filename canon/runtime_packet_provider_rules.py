from __future__ import annotations

FORBIDDEN_RUNTIME_PACKET_PROVIDER_METHODS: tuple[str, ...] = (
    "decide",
    "route_decision",
    "select_winner",
    "choose_winner",
    "execute_action",
    "dispatch_action",
)


def assert_runtime_packet_provider_api(method_names: tuple[str, ...]) -> None:
    forbidden = set(FORBIDDEN_RUNTIME_PACKET_PROVIDER_METHODS).intersection(method_names)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "runtime packet provider must remain a packet assembly primitive; "
            f"forbidden methods detected: {joined}"
        )
