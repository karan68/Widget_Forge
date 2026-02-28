"""
Clipboard History connector.
Polls the system clipboard and maintains a persistent history.
"""
import re
import json
import time
from datetime import datetime, timezone
from pathlib import Path

STORE_PATH = Path("backend/store/clipboard_history.json")
MAX_ITEMS = 8

def _load_history() -> list:
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text())
        except Exception:
            return []
    return []

def _save_history(items: list):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(items, indent=2))

def _detect_type(text: str) -> str:
    """Auto-detect content type."""
    if re.match(r"https?://", text):
        return "url"
    if re.match(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
        return "email"
    if re.match(r"[\+]?[\d\s\-\(\)]{7,15}$", text.strip()):
        return "phone"
    if any(kw in text for kw in ["def ", "function ", "const ", "class ", "import ", "var ", "{", "=>"]):
        return "code"
    if len(text) > 200:
        return "long_text"
    return "text"

def capture_clipboard() -> str | None:
    """Read current clipboard text (Windows) via PowerShell."""
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        return None
    except Exception:
        return None

def poll_clipboard() -> dict:
    """
    Capture current clipboard text and add to history if new.
    Returns the full clipboard history.
    """
    history = _load_history()
    current = capture_clipboard()

    if current and current.strip():
        text = current.strip()
        # Remove existing duplicate so re-copied text bubbles to top
        history = [h for h in history if h.get("text") != text]
        # Always insert new entry at the top
        entry = {
            "id": int(time.time() * 1000),
            "text": text[:500],  # Cap at 500 chars
            "full_length": len(text),
            "content_type": _detect_type(text),
            "pinned": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        history.insert(0, entry)
        # Trim: keep pinned + newest unpinned up to MAX_ITEMS
        pinned = [h for h in history if h.get("pinned")]
        unpinned = [h for h in history if not h.get("pinned")]
        history = pinned + unpinned[:max(MAX_ITEMS - len(pinned), 0)]
        _save_history(history)

    return {
        "type": "clipboard",
        "items": history[:MAX_ITEMS],
        "count": len(history),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def pin_clip(clip_id: int) -> dict:
    """Toggle pin on a clipboard item."""
    history = _load_history()
    for item in history:
        if item.get("id") == clip_id:
            item["pinned"] = not item.get("pinned", False)
            break
    _save_history(history)
    return poll_clipboard()

def delete_clip(clip_id: int) -> dict:
    """Remove a clipboard item."""
    history = _load_history()
    history = [h for h in history if h.get("id") != clip_id]
    _save_history(history)
    return poll_clipboard()

def clear_clipboard_history() -> dict:
    """Clear all non-pinned clipboard history."""
    history = _load_history()
    history = [h for h in history if h.get("pinned")]
    _save_history(history)
    return poll_clipboard()

def get_clipboard_history() -> dict:
    """Get clipboard history — also polls for new content."""
    return poll_clipboard()
