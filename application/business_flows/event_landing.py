"""Event landing builder (port of ClientPlatform event_landing_builder).

Pure. A landing is derived from an event title (the bookings slot title): a deterministic
template from slots and price, plus owner overrides stored as ``event_series@v1`` facts
(``landing_section`` / ``landing_theme`` / ``landing_published`` / ``landing_reset``).
AI drafting reuses the marketing LLM transport (Russian providers only) and only fills a
section of the unpublished draft; publishing is always an explicit owner step.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

CANON_EVENT_LANDING = True
SECTIONS = ("hero", "about", "for_whom", "program", "faq", "cta")
SECTION_LABELS = {
    "hero": "Заголовок",
    "about": "О встрече",
    "for_whom": "Для кого",
    "program": "Программа",
    "faq": "Вопросы",
    "cta": "Призыв",
}
THEMES = ("light", "dark", "warm")
MAX_SECTION = 1200
_WS = re.compile(r"\s+")


@dataclass
class Landing:
    key: str
    sections: dict[str, str] = field(default_factory=dict)
    theme: str = "light"
    published_version: int = 0
    version: int = 0


def key_for(title: str) -> str:
    k = _WS.sub(" ", str(title or "")).strip().casefold()[:120]
    if not k:
        raise ValueError("landing_title: /landing Название встречи")
    return k


def _clean(text: str) -> str:
    out = _WS.sub(" ", str(text or "").replace("\x00", " ")).strip()
    if not out:
        raise ValueError("landing_text_empty")
    return out[:MAX_SECTION]


def _sentences(text: str, n: int) -> str:
    """Donor _sentences: first n sentences of owner text."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n])


def replay(payloads: list[dict[str, Any]]) -> dict[str, Landing]:
    out: dict[str, Landing] = {}
    for p in payloads:
        step = str(p.get("step") or "")
        if not step.startswith("landing_"):
            continue
        ld = out.setdefault(str(p["key"]), Landing(str(p["key"])))
        if step == "landing_section" and p.get("section") in SECTIONS:
            ld.sections[str(p["section"])] = str(p["text"])
            ld.version += 1
        elif step == "landing_theme" and p.get("theme") in THEMES:
            ld.theme = str(p["theme"])
            ld.version += 1
        elif step == "landing_reset":
            ld.sections.clear()
            ld.theme = "light"
            ld.version += 1
        elif step == "landing_published":
            ld.published_version = int(p.get("version") or 0)
    return out


def template(title: str, slots: list[Any], *, price: str = "", fmt_slot: Any = str) -> dict[str, str]:
    """Donor build_event_landing_template: deterministic sections, no invented claims."""
    mine = [x for x in slots if key_for(x.title or "Встреча") == key_for(title)]
    free = [x for x in mine if x.status == "open"]
    dates = "\n".join(f"• {fmt_slot(x)}" for x in mine[:6]) or "Даты скоро появятся."
    return {
        "hero": title.strip()[:120],
        "about": f"Встреча «{title.strip()[:120]}». Подробности расскажет ведущий.",
        "for_whom": "Для тех, кому интересна тема встречи.",
        "program": dates,
        "faq": "Как записаться? — Нажмите кнопку записи и выберите время."
        + (f"\nСколько стоит? — {price}." if price else ""),
        "cta": f"Записаться ({len(free)} свободных мест)" if free else "Записаться в лист ожидания",
    }


def effective(title: str, ld: Landing | None, slots: list[Any], **kw: Any) -> dict[str, str]:
    base = template(title, slots, **kw)
    return {**base, **(ld.sections if ld else {})}


def preview(title: str, ld: Landing | None, slots: list[Any], **kw: Any) -> str:
    sec = effective(title, ld, slots, **kw)
    status = "черновик"
    if ld and ld.published_version:
        status = "опубликовано" if ld.published_version == ld.version else "опубликовано, есть новые правки"
    body = "\n\n".join(f"[{SECTION_LABELS[k]}]\n{sec[k]}" for k in SECTIONS)
    return f"🌐 Лендинг · {status} · тема {ld.theme if ld else 'light'}\n\n{body}"


def update_section(title: str, section: str, text: str) -> dict[str, Any]:
    s = section.strip().casefold()
    if s not in SECTIONS:
        raise ValueError("landing_section: " + ", ".join(SECTIONS))
    return {"step": "landing_section", "key": key_for(title), "section": s, "text": _clean(text)}


def set_theme(title: str, theme: str) -> dict[str, Any]:
    t = theme.strip().casefold()
    if t not in THEMES:
        raise ValueError("landing_theme: " + ", ".join(THEMES))
    return {"step": "landing_theme", "key": key_for(title), "theme": t}


def reset(title: str) -> dict[str, Any]:
    return {"step": "landing_reset", "key": key_for(title)}


def publish(title: str, ld: Landing | None) -> dict[str, Any] | None:
    """Idempotent: publishing the same version twice writes nothing."""
    version = ld.version if ld else 0
    if ld and ld.published_version == version and version:
        return None
    return {"step": "landing_published", "key": key_for(title), "version": max(version, 1)}


def ai_prompt(title: str, sections: dict[str, str]) -> tuple[str, str]:
    system = (
        "Ты помогаешь владельцу малого бизнеса написать текст лендинга встречи на русском. "
        "Не придумывай факты, цены, гарантии и отзывы. Ответ строго JSON: "
        '{"about": "...", "for_whom": "..."} не длиннее 600 символов каждое поле.'
    )
    user = json.dumps({"title": title[:120], "program": sections.get("program", "")[:600]}, ensure_ascii=False)
    return system, user


def parse_ai(text: str) -> dict[str, str]:
    """Strict JSON, fails closed; strips links; only about / for_whom may be filled."""
    try:
        data = json.loads(str(text or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("landing_ai_unparseable") from exc
    if not isinstance(data, dict):
        raise ValueError("landing_ai_unparseable")
    out = {}
    for k in ("about", "for_whom"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = re.sub(r"https?://\S+|www\.\S+", "", v)[:600].strip()
    if not out:
        raise ValueError("landing_ai_empty")
    return out


__all__ = [
    "CANON_EVENT_LANDING",
    "SECTIONS",
    "THEMES",
    "Landing",
    "ai_prompt",
    "effective",
    "key_for",
    "parse_ai",
    "preview",
    "publish",
    "replay",
    "reset",
    "set_theme",
    "template",
    "update_section",
]
