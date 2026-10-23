from __future__ import annotations

import json
import re

from dataclasses import dataclass

from core.llm.contracts import LLMMessage


@dataclass(frozen=True)
class CreativeBrief:
    business_type: str
    offer_title: str
    offer_details: str
    city: str = ""
    tone: str = "friendly"
    language: str = "ru"


def build_messages(brief: CreativeBrief) -> list[LLMMessage]:
    system = (
        "You are a marketing copywriter. Produce SAFE, factual ad copy. "
        "Avoid medical guarantees, shaming, and all-caps. Keep it short."
    )
    user = (
        f"Business: {brief.business_type}\n"
        f"Offer: {brief.offer_title}\n"
        f"Details: {brief.offer_details}\n"
        f"City: {brief.city}\n"
        f"Tone: {brief.tone}\n"
        "Return:\n"
        "- Headline (<=60 chars)\n"
        "- Primary text (<=200 chars)\n"
        "- Description (<=90 chars)\n"
        "- CTA one of: Learn More, Sign Up, Book Now\n"
    )
    return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]

SCENE_FIELDS = ("subject", "action", "setting", "mood", "light", "angle", "style", "palette", "before", "process", "after")
_CHANGE_VERB_RE = re.compile(r"превра|станов|стал[аио]?\b|преобра|обнов|восстан|трансформ|переде|меня[ею]т|был[аио]?\b", re.I)
_CHANGE_RE = re.compile(r"\b(?:из|от|был[аио]?)\s+(?P<before>[^,.;]{2,60}?)[,;]?\s+(?:в|во|до|стал[аио]?)\s+(?P<after>[^,.;]{2,60})", re.I)
_PROCESS_RE = re.compile(r"\b(?:с помощью|благодаря|после|за сч[её]т|через)\s+(?P<process>[^,.;]{2,60})", re.I)


def parse_scene_json(raw: object) -> dict[str, str] | None:
    """Strict art-director JSON; invalid output falls back to rules."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```"))
        except ValueError:
            return None
    if not isinstance(raw, dict) or not set(raw) <= set(SCENE_FIELDS) or not all(isinstance(v, str) for v in raw.values()):
        return None
    scene = {k: " ".join(v.split())[:120] for k, v in raw.items() if v.strip()}
    if not scene.get("subject") or bool(scene.get("before")) != bool(scene.get("after")):
        return None
    return scene


def scene_from_text(text: str) -> dict[str, str]:
    """Generic Russian change grammar, without domain-specific word lists."""
    clean = " ".join(str(text or "").split()).strip(" .")
    scene = {"subject": clean[:120]}
    if _CHANGE_VERB_RE.search(clean) and (match := _CHANGE_RE.search(clean)):
        scene.update(before=match["before"].strip(), after=_PROCESS_RE.sub("", match["after"]).strip())
        scene["subject"] = (clean[: match.start()].strip(" ,:—-") or clean)[:120]
        if process := _PROCESS_RE.search(clean):
            scene["process"] = process["process"].strip()
    return scene


def scene_key_elements(scene: dict[str, str]) -> list[str]:
    return [v for v in dict.fromkeys((scene.get("action") or scene.get("subject", ""), scene.get("after", ""))) if v]


def render_pack_idempotency_key(base_key: str, composition: dict[str, object], formats: list[str] | tuple[str, ...]) -> str:
    """Render idempotency bound to exact composition and formats (donor creative_studio.render_idempotency_key)."""
    import hashlib

    payload = json.dumps({"composition": dict(composition), "formats": list(formats)},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{base_key}:render:{hashlib.sha256(payload.encode()).hexdigest()[:32]}"
