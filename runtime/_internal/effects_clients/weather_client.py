from __future__ import annotations

from typing import Dict, Tuple

from runtime._internal.http_transport import HttpTransport
from runtime.observability.error_handling import swallow

from .http_client import http_json


def open_meteo_weather(city: str, *, transport: HttpTransport | None = None) -> tuple[bool, str, dict[str, object]]:
    try:
        city = str(city or "").strip()
        if not city:
            return False, "", {"error": "CITY_MISSING"}
        geo = http_json("GET", "https://geocoding-api.open-meteo.com/v1/search", {"name": city, "count": 1, "language": "ru", "format": "json"}, timeout_s=20, transport=transport)
        results = geo.get("results") if isinstance(geo, dict) else None
        if not isinstance(results, list) or not results:
            return False, "", {"error": "CITY_NOT_FOUND"}
        r0 = results[0] if isinstance(results[0], dict) else {}
        lat, lon = r0.get("latitude"), r0.get("longitude")
        if lat is None or lon is None:
            return False, "", {"error": "GEO_MISSING"}
        w = http_json("GET", "https://api.open-meteo.com/v1/forecast", {"latitude": lat, "longitude": lon, "current": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m", "timezone": "auto"}, timeout_s=20, transport=transport)
        cur = w.get("current") if isinstance(w, dict) else None
        if not isinstance(cur, dict):
            return False, "", {"error": "WEATHER_MISSING"}
        name, country = r0.get("name") or city, r0.get("country")
        loc = f"{name}" + (f", {country}" if country else "")
        txt = f"Погода сейчас в {loc}: {cur.get('temperature_2m')}°C (ощущается как {cur.get('apparent_temperature')}°C), осадки {cur.get('precipitation')} мм, ветер {cur.get('wind_speed_10m')} м/с."
        return True, txt, {"geo": r0, "weather": cur}
    except Exception as e:
        swallow(__name__, "open_meteo_weather")
        return False, "", {"error": str(e)[:200]}
