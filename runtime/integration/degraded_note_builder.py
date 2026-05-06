from __future__ import annotations


def build_missing_input_note(name: str) -> str:
    return f"degraded_input:{name}"


def append_note(notes: tuple[str, ...], note: str) -> tuple[str, ...]:
    if note in notes:
        return notes
    return (*notes, note)
