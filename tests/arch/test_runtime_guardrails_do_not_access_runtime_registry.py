from pathlib import Path


def test_runtime_guardrails_do_not_access_runtime_registry() -> None:
    text = Path("infra/runtime_guardrails.py").read_text(encoding="utf-8")

    forbidden = (
        "RuntimeRegistry",
        "ReadOnlyRuntimeRegistry",
        "registry.get(",
        "build_runtime(",
        "RuntimeCapabilityAccess",
    )
    for fragment in forbidden:
        assert fragment not in text
