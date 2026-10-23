"""Visual creatives (port of ClientPlatform visual_creatives / visual_aesthetic_director /
visual_style_preferences, image only).

Pure. A brief is compiled deterministically from owner facts (event title, landing "about",
style, format) and frozen by a content hash, so the same request never triggers a second paid
generation. Generation is an executor effect (``marketing_image_generate``) backed by YandexART
on fixed Yandex hosts. Video is not ported: no Russian video provider is on the allowlist.
Facts live under ``event_series@v1`` steps ``visual_style`` and ``visual_generated``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

CANON_VISUAL_CREATIVES = True
STYLES = {
    "photo": "реалистичная фотография, естественный свет, живые эмоции",
    "illustration": "мягкая цифровая иллюстрация, чистые формы",
    "minimal": "минимализм, много воздуха, спокойная палитра",
    "warm": "тёплая атмосфера, золотой час, уютные тона",
}
STYLE_LABELS = {"photo": "Фото", "illustration": "Иллюстрация", "minimal": "Минимализм", "warm": "Тёплый"}
FORMATS = {"post": (1, 1), "feed": (4, 5), "story": (9, 16), "wide": (16, 9)}
NEGATIVE = "текст, буквы, цифры, логотипы, водяные знаки, искажённые лица, лишние пальцы"
MAX_CONTEXT = 400
_WS = re.compile(r"\s+")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_FACT = re.compile(r"\d[\d.,:%₽$€-]*")
_LATIN = re.compile(r"[A-Za-z]{3,}")
_CAPS = re.compile(r"(?<=[^\s.!?]\s)[А-ЯЁ][а-яё]{2,}")


def _clean(text: object, limit: int = MAX_CONTEXT) -> str:
    return _WS.sub(" ", _URL.sub(" ", str(text or "").replace("\x00", " "))).strip()[:limit]


def key_for(title: str) -> str:
    k = _clean(title, 120).casefold()
    if not k:
        raise ValueError("visual_title: /visual Название встречи")
    return k


def invents_fact(text: str, *, owner_context: str) -> bool:
    """Donor invents_fact: numbers, Latin words and mid-sentence proper names must come from the owner."""
    ctx = owner_context.casefold()
    for pattern in (_FACT, _LATIN, _CAPS):
        for m in pattern.finditer(text):
            token = m.group(0).strip(" .,:-")
            if token and token.casefold() not in ctx:
                return True
    return False


def sanitize_direction(text: object, *, owner_context: str) -> str:
    """Donor sanitize_visual_direction: drop an art direction that invents facts."""
    value = _clean(text, 300)
    return "" if not value or invents_fact(value, owner_context=owner_context) else value


@dataclass(frozen=True)
class Brief:
    key: str
    prompt: str
    negative: str
    style: str
    fmt: str
    width_ratio: int
    height_ratio: int
    seed: int
    payload_key: str

    def to_mapping(self) -> dict[str, object]:
        return {"prompt": self.prompt, "negative": self.negative, "seed": self.seed,
                "width_ratio": self.width_ratio, "height_ratio": self.height_ratio}


def build_brief(title: str, *, context: str = "", style: str = "photo", fmt: str = "post", direction: str = "") -> Brief:
    """Donor build_business_image_brief / build_ad_visual_brief / freeze_*: deterministic, hash-frozen."""
    key = key_for(title)
    style, fmt = (style or "photo").strip().casefold(), (fmt or "post").strip().casefold()
    if style not in STYLES:
        raise ValueError("visual_style: " + ", ".join(STYLES))
    if fmt not in FORMATS:
        raise ValueError("visual_format: " + ", ".join(FORMATS))
    name, ctx = _clean(title, 120), _clean(context)
    extra = sanitize_direction(direction, owner_context=f"{name} {ctx}")
    parts = [f"Рекламное изображение для встречи «{name}»."]
    if ctx:
        parts.append(f"Контекст от владельца: {ctx}.")
    if extra:
        parts.append(f"Направление: {extra}.")
    parts.append(f"Стиль: {STYLES[style]}. Без текста и логотипов на изображении.")
    prompt = " ".join(parts)[:500]
    w, h = FORMATS[fmt]
    digest = hashlib.sha256(json.dumps([prompt, NEGATIVE, w, h], ensure_ascii=False).encode()).hexdigest()
    return Brief(key, prompt, NEGATIVE, style, fmt, w, h, int(digest[:8], 16) % 2_000_000_000, digest[:24])


@dataclass
class VisualState:
    styles: dict[str, str] = field(default_factory=dict)
    generated: dict[str, dict] = field(default_factory=dict)

    def for_title(self, key: str) -> list[dict]:
        return [g for g in self.generated.values() if g.get("key") == key]


def replay(facts: list[dict]) -> VisualState:
    st = VisualState()
    for f in facts:
        step = f.get("step")
        if step == "visual_style":
            st.styles[str(f["key"])] = str(f["style"])
        elif step == "visual_generated":
            st.generated.setdefault(str(f["payload_key"]), dict(f))
    return st


def save_style(title: str, style: str) -> dict:
    """Donor save_visual_style_preference."""
    style = (style or "").strip().casefold()
    if style not in STYLES:
        raise ValueError("visual_style: " + ", ".join(STYLES))
    return {"step": "visual_style", "key": key_for(title), "style": style}


def generated_fact(brief: Brief, *, path: str, size: int) -> dict:
    if not path or int(size) <= 0:
        raise ValueError("visual_result_empty")
    return {"step": "visual_generated", "key": brief.key, "payload_key": brief.payload_key,
            "style": brief.style, "fmt": brief.fmt, "path": str(path), "size": int(size)}


def parse_command(arg: str) -> tuple[str, str, str]:
    parts = [x.strip() for x in str(arg or "").split("|")]
    return parts[0], (parts[1].casefold() if len(parts) > 1 else ""), (parts[2].casefold() if len(parts) > 2 else "")
