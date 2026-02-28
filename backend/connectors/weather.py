"""
Weather connector — WeatherAPI.com (primary) + wttr.in (fallback).
Docs: https://www.weatherapi.com/docs/
"""
import httpx
from typing import List
from backend.config import settings

WEATHERAPI_BASE = "https://api.weatherapi.com/v1"
WTTR_BASE = "https://wttr.in"

# EPA AQI index → label + color hint
_AQI_LABELS = {
    1: ("Good", "Good"),
    2: ("Moderate", "Warning"),
    3: ("Unhealthy (SG)", "Warning"),
    4: ("Unhealthy", "Attention"),
    5: ("Very Unhealthy", "Attention"),
    6: ("Hazardous", "Attention"),
}


async def get_weather(cities: List[str] = None) -> dict:
    if not cities:
        cities = ["Hyderabad"]
    cleaned = [c.strip().strip(",") for c in cities if c.strip()]
    if not cleaned:
        cleaned = ["Hyderabad"]

    results = []
    for city in cleaned:
        data = None
        if settings.WEATHERAPI_KEY:
            data = await _weatherapi(city)
        if not data:
            data = await _wttr_weather(city)
        results.append(data)
    return {"cities": results, "count": len(results)}


async def _weatherapi(city: str) -> dict | None:
    """Fetch current weather + AQI from WeatherAPI.com."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{WEATHERAPI_BASE}/current.json",
                params={"key": settings.WEATHERAPI_KEY, "q": city, "aqi": "yes"},
            )
            r.raise_for_status()
            d = r.json()

        loc = d.get("location", {})
        cur = d.get("current", {})
        cond = cur.get("condition", {})
        aq = cur.get("air_quality", {})

        epa = aq.get("us-epa-index", 0)
        aqi_label, aqi_color = _AQI_LABELS.get(epa, ("N/A", "Default"))

        return {
            "city": loc.get("name", city),
            "region": loc.get("region", ""),
            "country": loc.get("country", ""),
            "localtime": loc.get("localtime", ""),
            "temp_c": str(round(cur.get("temp_c", 0))),
            "temp_f": str(round(cur.get("temp_f", 0))),
            "feels_like_c": str(round(cur.get("feelslike_c", 0))),
            "feels_like_f": str(round(cur.get("feelslike_f", 0))),
            "condition": cond.get("text", "Unknown"),
            "condition_icon": f"https:{cond.get('icon', '')}",
            "icon": _icon(cond.get("text", "")),
            "is_day": cur.get("is_day", 1),
            "humidity": str(cur.get("humidity", "?")),
            "cloud": str(cur.get("cloud", "?")),
            "wind_kph": str(cur.get("wind_kph", "?")),
            "wind_mph": str(round(cur.get("wind_mph", 0), 1)),
            "wind_dir": cur.get("wind_dir", ""),
            "pressure_mb": str(cur.get("pressure_mb", "?")),
            "vis_km": str(cur.get("vis_km", "?")),
            "uv_index": str(cur.get("uv", "?")),
            # Air quality
            "aqi_epa": epa,
            "aqi_label": aqi_label,
            "aqi_color": aqi_color,
            "pm2_5": str(round(aq.get("pm2_5", 0), 1)),
            "pm10": str(round(aq.get("pm10", 0), 1)),
        }
    except Exception as e:
        print(f"[Weather] WeatherAPI fail: {e}")
        return None


async def _wttr_weather(city: str) -> dict:
    """Fallback: wttr.in (no AQI)."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(f"{WTTR_BASE}/{city.replace(' ', '+')}",
                params={"format": "j1"},
                headers={"User-Agent": "WidgetForge/1.0", "Accept-Language": "en"})
            r.raise_for_status()
            d = r.json()
        cur = d.get("current_condition", [{}])[0]
        desc = cur.get("weatherDesc", [{}])[0].get("value", "Unknown")
        area = d.get("nearest_area", [{}])[0]
        name = area.get("areaName", [{}])[0].get("value", city)
        return {
            "city": name,
            "temp_c": cur.get("temp_C", "?"), "temp_f": cur.get("temp_F", "?"),
            "feels_like_c": cur.get("FeelsLikeC", "?"),
            "humidity": cur.get("humidity", "?"),
            "cloud": cur.get("cloudcover", "?"),
            "wind_kph": cur.get("windspeedKmph", "?"),
            "wind_mph": cur.get("windspeedMiles", "?"),
            "wind_dir": cur.get("winddir16Point", ""),
            "condition": desc, "icon": _icon(desc), "uv_index": cur.get("uvIndex", "?"),
            "aqi_epa": 0, "aqi_label": "N/A", "aqi_color": "Default",
            "pm2_5": "?", "pm10": "?",
        }
    except Exception as e:
        return {"city": city, "error": str(e), "condition": "Error"}


def _icon(cond: str) -> str:
    c = cond.lower()
    if "sunny" in c or "clear" in c: return "☀️"
    if "cloud" in c or "overcast" in c: return "☁️"
    if "rain" in c or "drizzle" in c: return "🌧️"
    if "snow" in c: return "❄️"
    if "thunder" in c or "storm" in c: return "⛈️"
    if "fog" in c or "mist" in c or "haze" in c: return "🌫️"
    if "wind" in c: return "💨"
    if "partly" in c: return "⛅"
    return "🌡️"
