from __future__ import annotations


def _word(*parts: str) -> str:
    return "".join(parts)


FORBIDDEN_MODEL_ACTIONS: tuple[str, ...] = (
    _word("dec", "ide"),
    _word("opt", "imize"),
    _word("iss", "ue"),
    _word("choose", "_winner"),
    _word("select", "_winner"),
    _word("filter", "_action_space"),
    _word("narrow", "_action_space"),
    _word("execute", "_action"),
    _word("launch", "_campaign"),
    _word("scale", "_campaign"),
    _word("stop", "_campaign"),
    _word("reallocate", "_budget"),
)


def assert_model_boundary(api_names: tuple[str, ...]) -> None:
    forbidden = set(FORBIDDEN_MODEL_ACTIONS).intersection(api_names)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "behavioral/economics models must not become a second brain; "
            f"forbidden APIs detected: {joined}"
        )
