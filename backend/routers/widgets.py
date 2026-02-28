import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.llm_service import parse_intent
from backend.services.entity_normalizer import enrich_intent_with_entity
from backend.services.credential_store import (
    check_widget_state, is_widget_configured, set_credentials,
    load_credentials_into_settings, reload_credentials_for,
    list_credentials, get_credential, delete_credential,
    set_widget_lifecycle_state, get_widget_lifecycle_state,
    get_credential_for,
)
from backend.services.widget_manifest import (
    WidgetState, get_manifest, list_all_manifests, list_manifests_needing_credentials,
    get_refresh_interval, get_credential_keys_for, validate_manifest,
    discover_plugins, get_discovery_errors,
)
from backend.services.card_templates import (
    bugs_by_priority_card, meetings_card, commits_card,
    weather_card, news_card, system_health_card,
    github_activity_card, standup_card, prs_card,
    process_metrics_card,
    stock_card, counter_card, link_card, checklist_card,
    note_card, countdown_card, tracker_card,
    timer_card, clock_card, cricket_card,
    gmail_card, google_meetings_card, youtube_card,
    battery_card, clipboard_card, my_day_card,
    disk_space_card, network_card, search_card,
    credential_setup_card, plane_card,
)
from backend.services.data_engine import fetch_data

router = APIRouter(prefix="/api/widgets", tags=["widgets"])

STORE_PATH = Path("backend/store/widgets.json")

def _load_store() -> list:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text())
    return []

def _save_store(widgets: list):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(widgets, indent=2))

# Template mapping - use these first (instant generation)
TEMPLATES = {
    ("ado", "bugs"): bugs_by_priority_card,
    ("ado", "work_items"): bugs_by_priority_card,
    ("google", "meetings"): google_meetings_card,
    ("google", "calendar"): google_meetings_card,
    ("google", "gmail"): gmail_card,
    ("google", "gmail_latest"): gmail_card,
    ("google", "gmail_summary"): gmail_card,
    ("github", "commits"): commits_card,
    ("github", "prs"): prs_card,
    ("github", "activity"): github_activity_card,
    ("github", "standup"): standup_card,
    ("weather", "weather"): weather_card,
    ("news", "stories"): news_card,
    ("news", "latest"): news_card,
    ("news", "crypto"): news_card,
    ("news", "market"): news_card,
    ("system", "health"): system_health_card,
    # New custom widget types
    ("stock", "price"): stock_card,
    ("custom", "counter"): counter_card,
    ("custom", "link"): link_card,
    ("custom", "checklist"): checklist_card,
    ("custom", "note"): note_card,
    ("custom", "countdown"): countdown_card,
    ("custom", "tracker"): tracker_card,
    ("custom", "timer"): timer_card,
    ("custom", "clock"): clock_card,
    ("cricket", "scores"): cricket_card,
    ("cricket", "live"): cricket_card,
    ("google", "youtube"): youtube_card,
    ("google", "youtube_search"): youtube_card,
    ("system", "battery"): battery_card,
    ("system", "clipboard"): clipboard_card,
    ("composite", "my_day"): my_day_card,
    ("system", "disk_space"): disk_space_card,
    ("system", "network"): network_card,
    ("search", "web"): search_card,
    ("search", "images"): search_card,
    ("search", "videos"): search_card,
    ("search", "news"): search_card,
    ("plane", "issues"): plane_card,
}

def _build_generic_card(intent: dict, data: dict) -> dict:
    """Build a generic card when no specific template exists."""
    body = [
        {"type": "TextBlock", "text": intent.get("title", "Widget"), "weight": "Bolder", "size": "Large"},
    ]
    
    # Add data items
    if isinstance(data, dict):
        for key, value in list(data.items())[:6]:
            if isinstance(value, (str, int, float, bool)):
                body.append({"type": "TextBlock", "text": f"**{key}:** {value}", "wrap": True, "size": "Small"})
            elif isinstance(value, list):
                body.append({"type": "TextBlock", "text": f"**{key}:** {len(value)} items", "wrap": True, "size": "Small"})
    
    body.append({
        "type": "TextBlock",
        "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
        "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True
    })
    
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body,
    }

class ForgeRequest(BaseModel):
    prompt: str
    use_llm_for_card: bool = False  # Only use LLM if explicitly requested

class RefreshRequest(BaseModel):
    widget_id: str

@router.post("/forge")
async def forge_widget(req: ForgeRequest):
    """Main endpoint: natural language → live widget. Uses templates by default (fast)."""
    t0 = time.time()

    # Step 1: Parse intent (rule-based or LLM)
    intent = await parse_intent(req.prompt)
    t1 = time.time()

    # Step 1b: Entity normalization (if intent needs an entity)
    intent = await enrich_intent_with_entity(intent, req.prompt)

    # Step 1c: Credential check — is this widget type configured?
    data_source = intent.get("data_source", "")
    state_info = check_widget_state(data_source)

    if state_info["state"] == WidgetState.UNCONFIGURED:
        # Widget needs credentials — return a setup card instead of data
        card = credential_setup_card(state_info)
        t2 = time.time()
        widget = {
            "id": str(uuid.uuid4())[:8],
            "prompt": req.prompt,
            "intent": intent,
            "adaptive_card": card,
            "data": {"state": "unconfigured", "data_source": data_source},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "refresh_minutes": 0,  # no auto-refresh for unconfigured widgets
            "timing": {
                "intent_parse_ms": int((t1 - t0) * 1000),
                "data_fetch_ms": 0,
                "card_gen_ms": int((t2 - t1) * 1000),
                "total_ms": int((t2 - t0) * 1000),
            }
        }
        store = _load_store()
        store.append(widget)
        _save_store(store)
        return widget

    # Step 2: Fetch live data
    data = await fetch_data(intent)
    t2 = time.time()

    # Step 2b: Check for fetch errors → DEGRADED state
    is_degraded = isinstance(data, dict) and ("error" in data or data.get("state") == "error")

    # Step 3: Generate Adaptive Card using TEMPLATE (instant, no LLM)
    # Check if this is process-specific data (has process_name field)
    if intent["data_source"] == "system" and "process_name" in data:
        template_func = process_metrics_card
    else:
        key = (intent["data_source"], intent["data_type"])
        template_func = TEMPLATES.get(key)
    
    if template_func:
        try:
            card = template_func(data)
        except Exception as e:
            card = _build_generic_card(intent, data)
    else:
        # No template for this type, use generic
        card = _build_generic_card(intent, data)
    
    t3 = time.time()

    # Step 3b: Determine refresh interval from manifest (enforces min_refresh_interval)
    manifest_interval = get_refresh_interval(data_source)
    intent_interval = intent.get("refresh_minutes", 5)
    # Use the larger of manifest minimum and intent request; 0 means no refresh
    if manifest_interval == 0:
        effective_refresh = 0
    elif is_degraded:
        effective_refresh = 0  # don't auto-refresh degraded widgets
    else:
        effective_refresh = max(manifest_interval, intent_interval) if intent_interval > 0 else manifest_interval

    # Step 4: Create widget config
    widget_state = WidgetState.DEGRADED if is_degraded else WidgetState.ACTIVE
    widget = {
        "id": str(uuid.uuid4())[:8],
        "prompt": req.prompt,
        "intent": intent,
        "adaptive_card": card,
        "data": data,
        "widget_state": widget_state,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "refresh_minutes": effective_refresh,
        "timing": {
            "intent_parse_ms": int((t1 - t0) * 1000),
            "data_fetch_ms": int((t2 - t1) * 1000),
            "card_gen_ms": int((t3 - t2) * 1000),
            "total_ms": int((t3 - t0) * 1000),
        }
    }

    # Step 5: Persist
    store = _load_store()
    store.append(widget)
    _save_store(store)

    # Step 5b: Persist lifecycle state
    set_widget_lifecycle_state(widget["id"], widget_state)

    return widget


@router.post("/refresh")
async def refresh_widget(req: RefreshRequest):
    """Refresh a widget's data and regenerate its card."""
    store = _load_store()
    widget = next((w for w in store if w["id"] == req.widget_id), None)
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")

    # Check lifecycle — don't refresh DISABLED, UNCONFIGURED, or DEGRADED widgets
    current_state = widget.get("widget_state", get_widget_lifecycle_state(req.widget_id))
    if current_state == WidgetState.DISABLED:
        raise HTTPException(status_code=409, detail="Widget is disabled")
    if current_state == WidgetState.UNCONFIGURED:
        raise HTTPException(status_code=409, detail="Widget needs configuration")
    if current_state == WidgetState.DEGRADED:
        raise HTTPException(status_code=409, detail="Widget is degraded — reconfigure or wait for recovery")

    # Re-fetch data
    data = await fetch_data(widget["intent"])

    # Check for errors → DEGRADED
    is_degraded = isinstance(data, dict) and ("error" in data or data.get("state") == "error")

    # Re-generate card using template (fast)
    key = (widget["intent"]["data_source"], widget["intent"]["data_type"])
    template_func = TEMPLATES.get(key)
    
    if template_func:
        try:
            card = template_func(data)
        except Exception:
            card = _build_generic_card(widget["intent"], data)
    else:
        card = _build_generic_card(widget["intent"], data)

    # Update widget state
    new_state = WidgetState.DEGRADED if is_degraded else WidgetState.ACTIVE
    widget["adaptive_card"] = card
    widget["data"] = data
    widget["widget_state"] = new_state
    widget["last_refreshed"] = datetime.now(timezone.utc).isoformat()

    # If degraded, stop auto-refresh
    if is_degraded:
        widget["refresh_minutes"] = 0

    _save_store(store)
    set_widget_lifecycle_state(req.widget_id, new_state)
    return widget


@router.get("/list")
async def list_widgets():
    """List all created widgets."""
    return _load_store()


@router.delete("/{widget_id}")
async def delete_widget(widget_id: str):
    """Delete a widget."""
    store = _load_store()
    store = [w for w in store if w["id"] != widget_id]
    _save_store(store)
    return {"deleted": widget_id}


# ─── Interactive Widget Actions ────────────────────────────────

class ActionRequest(BaseModel):
    widget_id: str
    action: str          # "increment", "decrement", "reset", "toggle", "add_item", "remove_item"
    payload: dict = {}   # Extra data: {"index": 0} for toggle, {"text": "..."} for add_item

def _regenerate_card(widget: dict) -> dict:
    """Regenerate the adaptive card from current data."""
    source = widget["intent"]["data_source"]
    dtype = widget["intent"].get("data_type", "")
    
    if source == "system" and "process_name" in widget.get("data", {}):
        return process_metrics_card(widget["data"])
    
    key = (source, dtype)
    template_func = TEMPLATES.get(key)
    if template_func:
        try:
            return template_func(widget["data"])
        except Exception:
            pass
    return _build_generic_card(widget["intent"], widget["data"])


@router.post("/action")
async def widget_action(req: ActionRequest):
    """Handle interactive widget actions (counter, checklist, timer)."""
    store = _load_store()
    widget = next((w for w in store if w["id"] == req.widget_id), None)
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    
    data = widget.get("data", {})
    widget_type = data.get("type", widget["intent"].get("data_type", ""))
    action = req.action
    
    # ── Counter actions ──
    if widget_type == "counter":
        if action == "increment":
            data["value"] = data.get("value", 0) + (req.payload.get("amount", 1))
        elif action == "decrement":
            data["value"] = data.get("value", 0) - (req.payload.get("amount", 1))
        elif action == "reset":
            data["value"] = 0
    
    # ── Checklist actions ──
    elif widget_type == "checklist":
        items = data.get("items", [])
        if action == "toggle":
            idx = req.payload.get("index", -1)
            if 0 <= idx < len(items):
                items[idx]["done"] = not items[idx].get("done", False)
        elif action == "add_item":
            text = req.payload.get("text", "").strip()
            if text:
                items.append({"text": text, "done": False})
        elif action == "remove_item":
            idx = req.payload.get("index", -1)
            if 0 <= idx < len(items):
                items.pop(idx)
        data["items"] = items
        data["total"] = len(items)
        data["completed"] = sum(1 for i in items if i.get("done", False))
    
    # ── Timer actions ──
    elif widget_type == "timer":
        if action == "start":
            data["running"] = True
        elif action == "pause":
            data["running"] = False
        elif action == "reset":
            data["remaining_seconds"] = data.get("total_seconds", 60)
            data["running"] = False
        elif action == "tick":
            # Decrement timer (called from frontend)
            if data.get("running", False) and data.get("remaining_seconds", 0) > 0:
                data["remaining_seconds"] = data.get("remaining_seconds", 0) - 1
                if data["remaining_seconds"] <= 0:
                    data["running"] = False
                    data["finished"] = True
    
    # ── Tracker actions ──
    elif widget_type == "tracker":
        items = data.get("items", [])
        if action == "increment":
            idx = req.payload.get("index", -1)
            if 0 <= idx < len(items):
                items[idx]["value"] = items[idx].get("value", 0) + 1
        elif action == "decrement":
            idx = req.payload.get("index", -1)
            if 0 <= idx < len(items):
                items[idx]["value"] = max(0, items[idx].get("value", 0) - 1)
        data["items"] = items
    
    # Update timestamp
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    widget["data"] = data
    
    # Regenerate the card
    widget["adaptive_card"] = _regenerate_card(widget)
    
    _save_store(store)
    return widget


@router.get("/card/{widget_id}")
async def get_widget_card(widget_id: str):
    """Return ONLY the adaptive card JSON for a widget (for Windows Widget Provider)."""
    store = _load_store()
    widget = next((w for w in store if w["id"] == widget_id), None)
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    return widget["adaptive_card"]


@router.get("/open")
async def open_in_explorer(path: str):
    """Open a file or folder in Windows Explorer."""
    import subprocess as sp
    from pathlib import Path as P
    from fastapi.responses import HTMLResponse

    target = P(path)
    if not target.exists():
        return HTMLResponse("<html><body><p>Path not found. <a href='javascript:window.close()'>Close</a></p></body></html>")

    try:
        if target.is_dir():
            sp.Popen(["explorer", str(target)])
        else:
            # Open Explorer with the file selected
            sp.Popen(["explorer", "/select,", str(target)])
    except Exception:
        pass

    # Return a self-closing page
    return HTMLResponse(
        "<html><body><script>window.close();</script>"
        "<p>Opening in Explorer... You can close this tab.</p></body></html>"
    )


@router.get("/types")
async def get_widget_types():
    """Return available widget types for the Windows Widget Picker."""
    return [
        {"id": "SystemHealth", "name": "System Health", "description": "Live CPU, RAM, Disk and Battery stats", "prompt": "Show system health"},
        {"id": "GitHubActivity", "name": "GitHub Activity", "description": "Your commits, PRs and code review status", "prompt": "Show my GitHub activity"},
        {"id": "HackerNews", "name": "Hacker News", "description": "Top tech news", "prompt": "Show Hacker News"},
        {"id": "Standup", "name": "Standup Prep", "description": "Yesterday's work summary", "prompt": "What did I work on yesterday"},
        {"id": "Counter", "name": "Counter", "description": "Interactive +1/-1 counter", "prompt": "Create a counter widget"},
        {"id": "Timer", "name": "Timer", "description": "Countdown timer with Start/Pause/Reset", "prompt": "Create a timer of 5 minutes"},
        {"id": "Clock", "name": "Clock", "description": "Live clock with date", "prompt": "Clock widget"},
        {"id": "Checklist", "name": "Checklist", "description": "Add, check, remove items", "prompt": "Checklist: item 1, item 2"},
        {"id": "Countdown", "name": "Countdown", "description": "Days/hours/min countdown", "prompt": "Countdown to March 15"},
        {"id": "Stock", "name": "Stock Price", "description": "Live stock price tracker", "prompt": "Track Adobe stock"},
        {"id": "Weather", "name": "Weather", "description": "Current weather", "prompt": "Weather in Hyderabad"},
        {"id": "Calendar", "name": "Calendar", "description": "Upcoming Google Calendar events", "prompt": "Show my upcoming meetings"},
        {"id": "Gmail", "name": "Gmail Inbox", "description": "Unread emails", "prompt": "Show my unread emails"},
    ]


@router.get("/google/status")
async def google_status():
    """Check if Google is authenticated."""
    from backend.connectors.google import is_authenticated, get_auth_url
    authed = is_authenticated()
    return {
        "authenticated": authed,
        "auth_url": get_auth_url() if not authed else None,
    }


@router.get("/suggestions")
async def get_widget_suggestions():
    """Scan the machine and suggest relevant widgets based on installed/running apps."""
    from backend.connectors.system import get_installed_apps
    
    apps = get_installed_apps()
    suggestions = []
    categories = apps.get("categories", {})
    
    # ── Essentials (always shown first) ──
    suggestions.extend([
        {"category": "Essentials", "prompt": "Show system health", "title": "System Monitor", "desc": "CPU, RAM, disk & battery live stats", "color": "#667eea"},
        {"category": "Essentials", "prompt": "Clock widget", "title": "Clock", "desc": "Live time with date", "color": "#51cf66"},
        {"category": "Essentials", "prompt": "Weather in Hyderabad", "title": "Weather", "desc": "Temperature, humidity & conditions", "color": "#ffd43b"},
        {"category": "Essentials", "prompt": "Create a timer of 25 minutes", "title": "Pomodoro", "desc": "25-min focus session timer", "color": "#ff6b6b"},
    ])

    # ── Google Calendar + Gmail ──
    from backend.connectors.google import is_authenticated as google_authed
    if google_authed():
        suggestions.extend([
            {"category": "Google", "prompt": "Show my upcoming meetings", "title": "Calendar", "desc": "Next 7 days of events", "color": "#4285f4"},
            {"category": "Google", "prompt": "Show my unread emails", "title": "Gmail Inbox", "desc": "Latest unread emails", "color": "#ea4335"},
            {"category": "Google", "prompt": "Gmail summary", "title": "Gmail Summary", "desc": "Unread count + latest", "color": "#ea4335"},
        ])
    else:
        suggestions.append(
            {"category": "Google", "prompt": "__auth_google__", "title": "Connect Google", "desc": "Calendar & Gmail widgets", "color": "#4285f4"}
        )
    
    # ── Smart suggestions per running app ──
    if categories.get("development"):
        suggestions.extend([
            {"category": "Dev", "prompt": "Show my GitHub activity", "title": "GitHub", "desc": "Commits, PRs & reviews today", "color": "#8b5cf6"},
            {"category": "Dev", "prompt": "What did I work on yesterday", "title": "Standup", "desc": "Prep your daily standup", "color": "#06b6d4"},
            {"category": "Dev", "prompt": "Show tech news", "title": "Tech News", "desc": "Latest technology headlines", "color": "#f97316"},
        ])
    
    if categories.get("communication"):
        suggestions.extend([
            {"category": "Work", "prompt": "Checklist: standup, review PRs, deploy, update docs", "title": "Daily Tasks", "desc": "Interactive work checklist", "color": "#10b981"},
            {"category": "Work", "prompt": "Countdown to March 31", "title": "Sprint End", "desc": "Days until sprint deadline", "color": "#ef4444"},
        ])
    
    if categories.get("media"):
        for app in categories["media"]:
            if "vlc" in app["name"].lower():
                suggestions.append({"category": "Media", "prompt": "Note: Watch later list", "title": "Watch Later", "desc": "Save shows to watch", "color": "#ff9800"})
    
    if categories.get("browsers"):
        browser = categories["browsers"][0]["name"]
        suggestions.append({"category": "Web", "prompt": f"Show CPU usage of {browser}", "title": f"{browser}", "desc": "Tabs eating your RAM?", "color": "#4285f4"})
    
    if categories.get("gaming"):
        suggestions.extend([
            {"category": "Gaming", "prompt": "Show system health", "title": "PC Monitor", "desc": "Watch temps while gaming", "color": "#9333ea"},
            {"category": "Gaming", "prompt": "Create a counter widget", "title": "Score Tracker", "desc": "Track wins & losses", "color": "#ec4899"},
        ])
    
    if categories.get("creative"):
        suggestions.extend([
            {"category": "Creative", "prompt": "Create a timer of 45 minutes", "title": "Deep Work", "desc": "45-min creative focus block", "color": "#f59e0b"},
            {"category": "Creative", "prompt": "Checklist: concept, sketch, refine, color, export", "title": "Design Flow", "desc": "Track your creative stages", "color": "#8b5cf6"},
        ])
    
    # ── Extra ideas ──
    suggestions.extend([
        {"category": "Essentials", "prompt": "Show battery health", "title": "Battery", "desc": "Charge, drain rate & health", "color": "#51cf66"},
        {"category": "Essentials", "prompt": "My day dashboard", "title": "My Day", "desc": "Calendar + email + weather", "color": "#667eea"},
        {"category": "Utility", "prompt": "Show clipboard history", "title": "Clipboard", "desc": "Recent copies & pastes", "color": "#06b6d4"},
        {"category": "Utility", "prompt": "Search for elon musk", "title": "Google Search", "desc": "Search the web", "color": "#4285f4"},
        {"category": "Utility", "prompt": "Show disk space", "title": "Disk Space", "desc": "Drive usage & cleanup tips", "color": "#f59e0b"},
        {"category": "Utility", "prompt": "Network speed test", "title": "Network", "desc": "Speed, ping & WiFi info", "color": "#10b981"},
        {"category": "Media", "prompt": "Play lofi beats", "title": "YouTube", "desc": "Search & play videos", "color": "#ff0000"},
        {"category": "Sports", "prompt": "Show live cricket scores", "title": "Cricket Live", "desc": "Live match scores", "color": "#22c55e"},
        {"category": "Finance", "prompt": "Track Microsoft stock", "title": "MSFT", "desc": "Microsoft stock price", "color": "#0078d4"},
        {"category": "Finance", "prompt": "Track Tesla stock", "title": "TSLA", "desc": "Tesla stock price", "color": "#cc0000"},
        {"category": "Utility", "prompt": "Create a counter widget", "title": "Counter", "desc": "Count anything", "color": "#667eea"},
        {"category": "Utility", "prompt": "Checklist: item 1, item 2, item 3", "title": "Checklist", "desc": "Add, check & remove", "color": "#10b981"},
        {"category": "Fun", "prompt": "Countdown to December 31", "title": "New Year", "desc": "Countdown to 2027", "color": "#ffd43b"},
    ])
    
    return {
        "suggestions": suggestions,
        "detected_apps": apps.get("running_apps", []),
        "app_count": apps.get("running_count", 0),
    }


# ─── Credential Management Endpoints ──────────────────────────

class CredentialSubmit(BaseModel):
    data_source: str
    credentials: dict  # {"CONFIG_KEY": "value", ...}

@router.post("/credentials")
async def save_credentials(req: CredentialSubmit):
    """Save credentials for a widget type. Entered by user via the setup UI."""
    manifest = get_manifest(req.data_source)
    if not manifest:
        raise HTTPException(status_code=400, detail=f"Unknown widget type: {req.data_source}")

    # Validate that the submitted keys match what the manifest expects
    expected_keys = set()
    for cap in manifest.get("capabilities", []):
        if cap.get("fields"):
            for f in cap["fields"]:
                expected_keys.add(f["key"])
        elif cap.get("config_keys"):
            expected_keys.update(cap["config_keys"])
        else:
            expected_keys.add(cap.get("config_key", ""))

    # Only store keys that are in the manifest (scoped access)
    valid_creds = {k: v for k, v in req.credentials.items() if k in expected_keys and v}

    if not valid_creds:
        raise HTTPException(status_code=400, detail="No valid credentials provided")

    # Save
    set_credentials(valid_creds)

    # Reload into settings so connectors pick them up immediately
    reload_credentials_for(req.data_source)

    # Validate credentials by attempting a lightweight fetch
    validation = {"tested": False, "valid": True, "message": "Credentials saved"}
    try:
        from backend.services.data_engine import fetch_data as _fetch
        test_intent = _get_test_intent(req.data_source)
        if test_intent:
            test_data = await _fetch(test_intent)
            if isinstance(test_data, dict) and ("error" in test_data or test_data.get("state") == "error"):
                validation = {"tested": True, "valid": False, "message": f"API returned error: {test_data.get('error', 'unknown')}"}
            else:
                validation = {"tested": True, "valid": True, "message": "Credentials verified successfully"}
    except Exception as e:
        validation = {"tested": True, "valid": False, "message": f"Validation failed: {str(e)[:100]}"}

    # Re-check state
    state_info = check_widget_state(req.data_source)

    return {
        "status": "saved",
        "data_source": req.data_source,
        "state": state_info["state"],
        "keys_saved": list(valid_creds.keys()),
        "validation": validation,
    }

@router.get("/credentials")
async def list_saved_credentials():
    """List all saved credentials (values masked)."""
    return {
        "credentials": list_credentials(),
        "manifests": [
            {
                "id": m["id"],
                "name": m["name"],
                "state": check_widget_state(m["id"])["state"],
                "capabilities": len(m.get("capabilities", [])),
            }
            for m in list_all_manifests()
            if m.get("capabilities")
        ],
    }

@router.delete("/credentials/{config_key}")
async def remove_credential(config_key: str):
    """Remove a specific credential."""
    delete_credential(config_key)
    return {"deleted": config_key}


class ReconfigureRequest(BaseModel):
    widget_id: str


def _get_test_intent(data_source: str) -> dict | None:
    """Return a minimal intent for testing credentials."""
    test_intents = {
        "news": {"data_source": "news", "data_type": "stories", "entity": "technology", "refresh_minutes": 0},
        "github": {"data_source": "github", "data_type": "activity", "entity": "", "refresh_minutes": 0},
        "ado": {"data_source": "ado", "data_type": "work_items", "entity": "", "refresh_minutes": 0},
        "plane": {"data_source": "plane", "data_type": "issues", "entity": "", "refresh_minutes": 0},
        "cricket": {"data_source": "cricket", "data_type": "scores", "entity": "", "refresh_minutes": 0},
        "search": {"data_source": "search", "data_type": "web", "entity": "test", "refresh_minutes": 0},
        "weather": {"data_source": "weather", "data_type": "weather", "entity": "London", "refresh_minutes": 0},
    }
    return test_intents.get(data_source)


class ToggleWidgetRequest(BaseModel):
    widget_id: str
    enabled: bool


@router.post("/toggle")
async def toggle_widget(req: ToggleWidgetRequest):
    """Enable or disable a widget (DISABLED ↔ ACTIVE/CONFIGURED)."""
    store = _load_store()
    widget = next((w for w in store if w["id"] == req.widget_id), None)
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")

    if req.enabled:
        # Re-enable: set to CONFIGURED (will become ACTIVE after next refresh)
        data_source = widget["intent"].get("data_source", "")
        state_info = check_widget_state(data_source)
        new_state = state_info["state"]  # CONFIGURED or UNCONFIGURED
        widget["widget_state"] = new_state
        # Restore refresh interval from manifest
        widget["refresh_minutes"] = get_refresh_interval(data_source)
    else:
        # Disable
        new_state = WidgetState.DISABLED
        widget["widget_state"] = WidgetState.DISABLED
        widget["refresh_minutes"] = 0

    _save_store(store)
    set_widget_lifecycle_state(req.widget_id, new_state)
    return widget

@router.post("/reconfigure")
async def reconfigure_widget(req: ReconfigureRequest):
    """
    Reset credentials for a widget and return the setup card so the user
    can re-enter their API keys (e.g. when a key expires or was wrong).
    """
    store = _load_store()
    widget = next((w for w in store if w["id"] == req.widget_id), None)
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")

    data_source = widget["intent"].get("data_source", "")
    manifest = get_manifest(data_source)
    if not manifest or not manifest.get("capabilities"):
        raise HTTPException(status_code=400, detail="This widget does not use credentials")

    # Delete all credential keys owned by this widget type
    for cap in manifest.get("capabilities", []):
        if cap.get("fields"):
            for f in cap["fields"]:
                if not f.get("default"):          # don't wipe defaults
                    delete_credential(f["key"])
        elif cap.get("config_keys"):
            for k in cap["config_keys"]:
                delete_credential(k)
        else:
            delete_credential(cap.get("config_key", ""))

    # Also clear runtime settings so connectors don't use stale values
    try:
        from backend.config import settings as _settings
        for cap in manifest.get("capabilities", []):
            if cap.get("fields"):
                for f in cap["fields"]:
                    if not f.get("default"):
                        setattr(_settings, f["key"], "")
            elif cap.get("config_keys"):
                for k in cap["config_keys"]:
                    setattr(_settings, k, "")
            else:
                setattr(_settings, cap.get("config_key", ""), "")
    except Exception:
        pass

    # Rebuild widget as a credential-setup card
    state_info = check_widget_state(data_source)
    card = credential_setup_card(state_info)
    widget["adaptive_card"] = card
    widget["data"] = {"state": "unconfigured", "data_source": data_source}
    widget["widget_state"] = WidgetState.UNCONFIGURED
    widget["refresh_minutes"] = 0
    _save_store(store)

    # Persist lifecycle state
    set_widget_lifecycle_state(req.widget_id, WidgetState.UNCONFIGURED)

    return widget

@router.get("/manifests")
async def get_all_manifests():
    """Return all widget manifests with their current state."""
    result = []
    for m in list_all_manifests():
        state_info = check_widget_state(m["id"])
        result.append({
            **m,
            "state": state_info["state"],
            "missing": [c["service_name"] for c in state_info["missing"]],
        })
    return result


@router.get("/manifests/validate")
async def validate_all_manifests():
    """Validate all registered manifests and return any errors."""
    results = []
    for m in list_all_manifests():
        errors = validate_manifest(m)
        results.append({
            "id": m.get("id", "unknown"),
            "name": m.get("name", ""),
            "valid": len(errors) == 0,
            "errors": errors,
        })
    return {"manifests": results, "plugin_errors": get_discovery_errors()}