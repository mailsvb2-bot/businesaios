from __future__ import annotations


def tokenize_text(text: str) -> set[str]:
    normalized = text.replace("_", " ").replace("-", " ").lower()
    return {part.strip() for part in normalized.split() if part.strip()}


def jaccard_similarity(left: str, right: str) -> float:
    left_tokens = tokenize_text(left)
    right_tokens = tokenize_text(right)
    if not left_tokens and not right_tokens:
        return 1.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(union), 6)
