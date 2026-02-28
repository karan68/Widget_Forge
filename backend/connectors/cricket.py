"""
Cricket connector using Free Cricbuzz Cricket API (RapidAPI).
Uses the /cricket-schedule endpoint to fetch upcoming & live matches.
"""
import httpx
from datetime import datetime, timezone
from backend.config import settings

CRICBUZZ_HOST = "free-cricbuzz-cricket-api.p.rapidapi.com"
CRICBUZZ_BASE = f"https://{CRICBUZZ_HOST}"

_HEADERS = lambda: {
    "x-rapidapi-host": CRICBUZZ_HOST,
    "x-rapidapi-key": settings.RAPIDAPI_KEY,
}


def _parse_schedule(raw: dict) -> list[dict]:
    """Flatten the nested schedule response into a clean match list."""
    matches: list[dict] = []
    schedules = raw.get("response", {}).get("schedules", [])
    for sched in schedules:
        wrapper = sched.get("scheduleAdWrapper") or {}
        date_label = wrapper.get("date", "")
        for series_block in wrapper.get("matchScheduleList", []):
            series_name = series_block.get("seriesName", "")
            for mi in series_block.get("matchInfo", []):
                t1 = mi.get("team1", {})
                t2 = mi.get("team2", {})
                venue = mi.get("venueInfo", {})
                start_ms = mi.get("startDate")
                start_dt = (
                    datetime.fromtimestamp(int(start_ms) / 1000, tz=timezone.utc)
                    if start_ms else None
                )
                matches.append({
                    "match_id":    mi.get("matchId"),
                    "series":      series_name,
                    "description": mi.get("matchDesc", ""),
                    "format":      mi.get("matchFormat", ""),
                    "date_label":  date_label,
                    "start":       start_dt.strftime("%b %d, %H:%M UTC") if start_dt else "",
                    "state":       mi.get("state", ""),
                    "status":      mi.get("status", ""),
                    "team1":       t1.get("teamName", "TBC"),
                    "team1_short": t1.get("teamSName", ""),
                    "team2":       t2.get("teamName", "TBC"),
                    "team2_short": t2.get("teamSName", ""),
                    "venue":       venue.get("ground", ""),
                    "city":        venue.get("city", ""),
                    "country":     venue.get("country", ""),
                })
    return matches


async def get_cricket_schedule(limit: int = 10) -> dict:
    """Fetch upcoming cricket schedule from Cricbuzz."""
    if not settings.RAPIDAPI_KEY:
        return {"error": "No RapidAPI key configured", "matches": []}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{CRICBUZZ_BASE}/cricket-schedule",
                headers=_HEADERS(),
            )
            r.raise_for_status()
            data = r.json()
        matches = _parse_schedule(data)[:limit]
        return {"matches": matches, "count": len(matches)}
    except Exception as e:
        return {"error": str(e), "matches": []}


async def get_cricket_scores() -> dict:
    """Get cricket matches — uses the schedule endpoint (the only reliable one)."""
    return await get_cricket_schedule(limit=10)
