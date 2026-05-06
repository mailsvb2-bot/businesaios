from __future__ import annotations

import json
import re
from typing import Any, Dict, Tuple

_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_block(text: str) -> Tuple[Dict[str, Any], str]:
    if not text:
        return {}, ""
    m = _JSON_BLOCK.search(text)
    if not m:
        return {}, text.strip()
    raw = m.group(1)
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    rest = (text[: m.start()] + text[m.end() :]).strip()
    return (data if isinstance(data, dict) else {}), rest
