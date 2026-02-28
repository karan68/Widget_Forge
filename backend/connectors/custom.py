"""
Custom widget data handler.
Handles custom/static widget types that don't need external APIs:
- counter, link/bookmark, checklist, note, countdown, tracker
"""
import re
from datetime import datetime, timezone, timedelta


def get_custom_data(intent: dict) -> dict:
    """
    Build data for custom widget types based on intent.
    These are static/local widgets that don't call external APIs.
    """
    data_type = intent.get("data_type", "note")
    
    if data_type == "counter":
        return _build_counter_data(intent)
    elif data_type == "link":
        return _build_link_data(intent)
    elif data_type == "checklist":
        return _build_checklist_data(intent)
    elif data_type == "note":
        return _build_note_data(intent)
    elif data_type == "countdown":
        return _build_countdown_data(intent)
    elif data_type == "tracker":
        return _build_tracker_data(intent)
    elif data_type == "timer":
        return _build_timer_data(intent)
    elif data_type == "clock":
        return _build_clock_data(intent)
    else:
        return _build_note_data(intent)


def _build_counter_data(intent: dict) -> dict:
    """Counter widget - tracks a number."""
    return {
        "title": intent.get("title", "Counter"),
        "value": intent.get("initial_value", 0) or 0,
        "type": "counter",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_link_data(intent: dict) -> dict:
    """Link/bookmark widget - displays a URL with preview info."""
    url = intent.get("url", "")
    
    # Try to extract useful info from URL
    domain = ""
    link_type = "link"
    embed_url = None
    
    if url:
        # Extract domain
        domain_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        domain = domain_match.group(1) if domain_match else url
        
        # Detect link type for rich display
        if "youtube.com" in url or "youtu.be" in url:
            link_type = "youtube"
            # Extract video ID for embed
            vid_match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
            if vid_match:
                embed_url = f"https://img.youtube.com/vi/{vid_match.group(1)}/mqdefault.jpg"
        elif "twitter.com" in url or "x.com" in url:
            link_type = "twitter"
        elif "github.com" in url:
            link_type = "github"
        elif "reddit.com" in url:
            link_type = "reddit"
        elif "linkedin.com" in url:
            link_type = "linkedin"
        elif "docs.google.com" in url:
            link_type = "google_doc"
        elif "figma.com" in url:
            link_type = "figma"
        elif "notion.so" in url or "notion.site" in url:
            link_type = "notion"
    
    return {
        "title": intent.get("title", f"{link_type.title()} Link"),
        "url": url,
        "domain": domain,
        "link_type": link_type,
        "embed_url": embed_url,
        "type": "link",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_checklist_data(intent: dict) -> dict:
    """Checklist/to-do widget."""
    items = intent.get("items", [])
    if not items:
        # Try to extract from content
        content = intent.get("content", "")
        if content:
            items = [item.strip() for item in content.split(",") if item.strip()]
    
    checklist = [{"text": item, "done": False} for item in items]
    
    return {
        "title": intent.get("title", "Checklist"),
        "items": checklist,
        "total": len(checklist),
        "completed": 0,
        "type": "checklist",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_note_data(intent: dict) -> dict:
    """Note/reminder widget."""
    return {
        "title": intent.get("title", "Note"),
        "content": intent.get("content", ""),
        "type": "note",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_countdown_data(intent: dict) -> dict:
    """Countdown/timer widget."""
    target_str = intent.get("target_date", "")
    
    if target_str:
        try:
            target = datetime.fromisoformat(target_str.replace("Z", "+00:00"))
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            target = datetime.now(timezone.utc) + timedelta(days=7)
    else:
        target = datetime.now(timezone.utc) + timedelta(days=7)
    
    now = datetime.now(timezone.utc)
    delta = target - now
    days_left = max(0, delta.days)
    hours_left = max(0, delta.seconds // 3600)
    
    return {
        "title": intent.get("title", "Countdown"),
        "target_date": target.isoformat(),
        "days_left": days_left,
        "hours_left": hours_left,
        "is_past": delta.total_seconds() < 0,
        "type": "countdown",
        "timestamp": now.isoformat(),
    }


def _build_tracker_data(intent: dict) -> dict:
    """Generic tracker widget."""
    items = intent.get("items", [])
    if not items:
        content = intent.get("content", "")
        if content:
            items = [item.strip() for item in content.split(",") if item.strip()]
    
    tracking = [{"label": item, "value": 0} for item in items]
    
    return {
        "title": intent.get("title", "Tracker"),
        "items": tracking,
        "type": "tracker",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_timer_data(intent: dict) -> dict:
    """Timer widget - counts down from N seconds."""
    # Extract seconds from intent
    seconds = intent.get("seconds") or intent.get("initial_value") or 60
    if isinstance(seconds, str):
        try:
            seconds = int(seconds)
        except ValueError:
            seconds = 60
    
    # Also check title for time hints
    title = intent.get("title", "")
    if not seconds or seconds == 60:
        import re as _re
        time_match = _re.search(r'(\d+)\s*(sec|second|min|minute|hour|hr)', title.lower() + " " + str(intent.get("content", "")))
        if time_match:
            val = int(time_match.group(1))
            unit = time_match.group(2)
            if "min" in unit:
                seconds = val * 60
            elif "hour" in unit or "hr" in unit:
                seconds = val * 3600
            else:
                seconds = val
    
    return {
        "title": intent.get("title", "Timer"),
        "total_seconds": seconds,
        "remaining_seconds": seconds,
        "running": False,
        "finished": False,
        "type": "timer",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_clock_data(intent: dict) -> dict:
    """Clock widget - shows current time."""
    now = datetime.now(timezone.utc)
    return {
        "title": intent.get("title", "Clock"),
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%B %d, %Y"),
        "timezone": "UTC",
        "type": "clock",
        "timestamp": now.isoformat(),
    }
