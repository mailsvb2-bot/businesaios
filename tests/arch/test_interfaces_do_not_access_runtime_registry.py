from __future__ import annotations

from pathlib import Path

from scripts.ci.repository_sources import read_python_source


def test_interfaces_do_not_access_runtime_registry() -> None:
    violations: list[str] = []

    for root in (Path("interfaces/api"), Path("interfaces/telegram")):
        if not root.exists():
            continue

        for path in sorted(root.rglob("*.py")):
            text = read_python_source(path)
            forbidden_fragments = (
                "registry.get(",
                "build_runtime(",
                "RuntimeRegistry",
                "ReadOnlyRuntimeRegistry",
                "RuntimeCapabilityAccess",
            )
            for fragment in forbidden_fragments:
                if fragment in text:
                    violations.append(
                        f"{path.as_posix()} contains forbidden runtime access "
                        f"fragment '{fragment}'"
                    )

    assert not violations, "\n".join(violations)
