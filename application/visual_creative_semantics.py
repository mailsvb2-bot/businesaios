from __future__ import annotations

import json
from typing import Any

_UNSAFE_DIRECTION_PHRASES = (
    "replace ", "remove ", "ignore ", "instead of", "different animal",
    "different subject", "different object", "swap ", "substitute ",
)


def safe_ai_direction_text(direction: object) -> str | None:
    text = " ".join(str(direction or "").replace("\x00", " ").split()).strip()
    if not text:
        return None
    folded = text.casefold()
    if any(phrase in folded for phrase in _UNSAFE_DIRECTION_PHRASES):
        return None
    return text[:1200]


def json_object_from_model(raw: object) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().casefold() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def grounded_visual_prompt(*, owner_request: object, art_direction: object = "") -> str:
    request = " ".join(str(owner_request or "").replace("\x00", " ").split()).strip()
    if not request:
        raise ValueError("visual owner request must not be empty")
    direction = safe_ai_direction_text(art_direction)
    guard = (
        "Preserve the requested subject, action, cause, transition and result exactly; "
        "art direction may change only composition, camera, staging, lighting, atmosphere and visual rhythm."
    )
    parts = [request]
    if direction:
        parts.append(direction)
    parts.append(guard)
    return "\n\n".join(parts)[:4000]


def parse_art_direction_variants(raw: object) -> tuple[dict[str, str], ...] | None:
    value = json_object_from_model(raw)
    items = value.get("variants") if value is not None else None
    if not isinstance(items, list) or len(items) != 5:
        return None
    required = {"title", "description", "direction", "composition"}
    allowed_compositions = {"clear_story", "cinematic", "editorial", "focused", "sequential"}
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not required.issubset(item):
            return None
        composition = str(item.get("composition") or "").strip().lower()
        direction = safe_ai_direction_text(item.get("direction"))
        if composition not in allowed_compositions or composition in seen or direction is None:
            return None
        seen.add(composition)
        result.append({
            "title": " ".join(str(item["title"]).split())[:80],
            "description": " ".join(str(item["description"]).split())[:500],
            "direction": direction,
            "composition": composition,
        })
    return tuple(result) if seen == allowed_compositions else None


__all__ = ["grounded_visual_prompt", "json_object_from_model", "parse_art_direction_variants", "safe_ai_direction_text"]
