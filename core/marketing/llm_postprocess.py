from __future__ import annotations

"""Small post-processing helpers for LLM marketing output."""


def normalize_generated_text(text: str) -> str:
    return str(text or "").strip()
