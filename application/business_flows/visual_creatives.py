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
        return {
            "prompt": self.prompt,
            "negative": self.negative,
            "seed": self.seed,
            "width_ratio": self.width_ratio,
            "height_ratio": self.height_ratio,
        }


def build_brief(
    title: str, *, context: str = "", style: str = "photo", fmt: str = "post", direction: str = ""
) -> Brief:
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
    return {
        "step": "visual_generated",
        "key": brief.key,
        "payload_key": brief.payload_key,
        "style": brief.style,
        "fmt": brief.fmt,
        "path": str(path),
        "size": int(size),
    }


def parse_command(arg: str) -> tuple[str, str, str]:
    parts = [x.strip() for x in str(arg or "").split("|")]
    return parts[0], (parts[1].casefold() if len(parts) > 1 else ""), (parts[2].casefold() if len(parts) > 2 else "")


# --- frozen scene/binding readers, variant ranking, image normalization (donor visual_creatives) ---

QA_RANK = {"pass": 3, "unavailable": 1, "needs_review": 0}
EVENT_BINDING_KEYS = frozenset({"type", "event_id", "stage", "slot_key", "kind"})
MAX_IMAGE_SIDE, MAX_IMAGE_PIXELS = 8192, 40_000_000


def _payload(value: object) -> dict:
    try:
        raw = json.loads(str(value or ""))
    except json.JSONDecodeError as exc:
        raise ValueError("frozen business visual payload is invalid") from exc
    if not isinstance(raw, dict):
        raise ValueError("frozen business visual payload is invalid")
    return raw


def frozen_scene(value: str):  # noqa: ANN201 - returns visual_scene types
    """Exact frozen scene of a v4+ receipt: restyling must never silently replan the content."""
    from application.business_flows.visual_scene import VisualSceneContract, VisualSceneVariant

    raw = _payload(value)
    if int(raw.get("version") or 0) < 4:
        return None
    brief, intent = raw.get("brief"), raw.get("intent")
    if not isinstance(brief, dict) or not isinstance(intent, dict):
        raise ValueError("frozen business visual scene is invalid")
    contract = VisualSceneContract.from_mapping(brief.get("scene_contract"))
    source = str(intent.get("scene_planner_source") or "").strip().lower()
    if source not in {"ai", "deterministic"}:
        raise ValueError("frozen business visual scene planner is invalid")
    variant = intent.get("scene_variant")
    return contract, source, None if variant is None else VisualSceneVariant.from_mapping(variant)


def frozen_binding(value: str) -> dict[str, str] | None:
    """Event-content binding of a frozen receipt; legacy receipts without a binding stay deliverable."""
    raw = _payload(value)
    binding = raw.get("binding")
    if binding is None:
        return None
    if not isinstance(binding, dict):
        raise ValueError("frozen business visual binding is invalid")
    norm = {str(k): str(v) for k, v in binding.items()}
    if set(norm) != EVENT_BINDING_KEYS or norm["type"] != "event_content":
        raise ValueError("frozen business visual binding is invalid")
    if norm["kind"] != str(raw.get("kind") or "image"):
        raise ValueError("frozen business visual binding kind mismatch")
    return norm


def best_candidate(candidates: list[dict]) -> dict | None:
    """Donor _best_image_variant ranking over executor ``candidates``: first succeeded image with the best
    semantic-QA rank wins (pass short-circuits); with no success the first job is kept."""
    best, best_rank = None, -1
    for job in candidates:
        if best is None:
            best = job
        if job.get("status") != "succeeded":
            continue
        rank = QA_RANK.get(str(job.get("semantic_qa") or "unavailable"), 0)
        if rank > best_rank or best.get("status") != "succeeded":
            best, best_rank = job, rank
        if rank == QA_RANK["pass"]:
            break
    return best


def validate_image_dimensions(size: tuple[int, int]) -> None:
    w, h = size
    if w < 64 or h < 64 or w > MAX_IMAGE_SIDE or h > MAX_IMAGE_SIDE or w * h > MAX_IMAGE_PIXELS:
        raise ValueError("visual_creative_invalid_image_dimensions")


def background_repair_box(image):  # noqa: ANN001, ANN201 - PIL image in, crop box out
    """Conservative crop for pathological one-sided blank padding (>=50% of a side); copy space survives."""
    from PIL import Image, ImageChops, ImageStat

    validate_image_dimensions(image.size)
    width, height = image.size
    probe = image.convert("RGB")
    probe.thumbnail((256, 256), Image.Resampling.LANCZOS)
    pw, ph = probe.size
    bh, bw = max(4, ph // 6), max(4, pw // 6)
    bands = (
        probe.crop((0, 0, pw, bh)),
        probe.crop((0, ph - bh, pw, ph)),
        probe.crop((0, 0, bw, ph)),
        probe.crop((pw - bw, 0, pw, ph)),
    )
    quiet = min((ImageStat.Stat(b) for b in bands), key=lambda s: max(s.stddev or [999.0]))
    if max(quiet.stddev or [999.0]) > 8.0:
        return None
    bg = tuple(int(round(v)) for v in quiet.mean[:3])
    diff = ImageChops.difference(probe, Image.new("RGB", probe.size, bg))
    cmax = ImageChops.lighter(ImageChops.lighter(diff.getchannel("R"), diff.getchannel("G")), diff.getchannel("B"))
    bbox = cmax.point(lambda v: 255 if v >= 18 else 0).getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    if max((ph - bottom) / ph, top / ph, left / pw, (pw - right) / pw) < 0.50:
        return None
    sx, sy = width / pw, height / ph
    crop = [max(0, int(left * sx)), max(0, int(top * sy)), min(width, int(right * sx)), min(height, int(bottom * sy))]
    mx, my = max(8, int(max(1, crop[2] - crop[0]) * 0.08)), max(8, int(max(1, crop[3] - crop[1]) * 0.08))
    crop = [max(0, crop[0] - mx), max(0, crop[1] - my), min(width, crop[2] + mx), min(height, crop[3] + my)]
    return None if (crop[2] - crop[0]) * (crop[3] - crop[1]) >= width * height * 0.82 else tuple(crop)


def normalize_image(path, *, repair_blank_bands: bool = True):  # noqa: ANN001, ANN201 - pathlib.Path
    """Verify, EXIF-orient, trim transparent/blank bands, flatten to RGB and re-encode in place.

    Pillow is optional (imported lazily); without it ``visual_creative_image_runtime_unavailable``.
    """
    import os

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ValueError("visual_creative_image_runtime_unavailable") from exc
    tmp = path.with_suffix(path.suffix + ".normalized.tmp")
    try:
        with Image.open(path) as opened:
            validate_image_dimensions(opened.size)
            opened.verify()
        with Image.open(path) as opened:
            validate_image_dimensions(opened.size)
            fmt = str(opened.format or "").upper()
            image = ImageOps.exif_transpose(opened)
            validate_image_dimensions(image.size)
            image.load()
            if "A" not in image.getbands() and "transparency" in image.info:
                image = image.convert("RGBA")
            alpha = image.getchannel("A") if "A" in image.getbands() else None
            abox = alpha.point(lambda v: 255 if v >= 16 else 0).getbbox() if alpha is not None else None
            if alpha is not None and abox is None:
                raise ValueError("visual_creative_invalid_image_asset")
            if abox is not None and abox != (0, 0, image.width, image.height):
                visible = image.crop(abox)
                if visible.width * visible.height < image.width * image.height * 0.82:
                    image = visible
            if "A" in image.getbands():
                flat = Image.new("RGB", image.size, (255, 255, 255))
                flat.paste(image, mask=image.getchannel("A"))
                image = flat
            else:
                image = image.convert("RGB")
            box = background_repair_box(image) if repair_blank_bands else None
            if box is not None:
                image = image.crop(box)
            if image.width < 64 or image.height < 64:
                raise ValueError("visual_creative_invalid_image_dimensions")
            suffix = path.suffix.lower()
            if suffix in {".jpg", ".jpeg"} or fmt in {"JPG", "JPEG"}:
                image.save(tmp, format="JPEG", quality=94, optimize=True)
            elif suffix == ".webp" or fmt == "WEBP":
                image.save(tmp, format="WEBP", quality=94, method=6)
            else:
                image.save(tmp, format="PNG", optimize=True)
        os.replace(tmp, path)
        return path
    except ValueError as exc:
        tmp.unlink(missing_ok=True)
        if str(exc).startswith("visual_creative_"):
            raise
        raise ValueError("visual_creative_invalid_image_asset") from exc
    except (OSError, Image.DecompressionBombError) as exc:
        tmp.unlink(missing_ok=True)
        raise ValueError("visual_creative_invalid_image_asset") from exc
