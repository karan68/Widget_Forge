"""
Google Calendar + Gmail connector using OAuth 2.0 Authorization Code flow.
Handles token management, calendar events, and Gmail inbox.
"""

import json
import os
import time
import httpx
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from backend.config import settings

TOKEN_FILE = "backend/store/google_token.json"

SCOPES = [
    # User info
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    # Gmail (readonly + modify + send + compose + labels)
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
    # Calendar (full CRUD + free/busy + list + settings)
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.settings.readonly",
    # YouTube (search + read)
    "https://www.googleapis.com/auth/youtube.readonly",
]

AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"

# ─── Token management ─────────────────────────────────────────

_token_cache = {}


def _load_token():
    """Load token from disk."""
    global _token_cache
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                _token_cache = json.load(f)
        except Exception:
            _token_cache = {}


def _save_token():
    """Persist token to disk."""
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(_token_cache, f, indent=2)


def get_auth_url() -> str:
    """Generate Google OAuth authorization URL."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    global _token_cache
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(TOKEN_URL, data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
            if resp.status_code != 200:
                return {"error": f"Token exchange failed: {resp.text}"}

            data = resp.json()
            _token_cache = {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", _token_cache.get("refresh_token", "")),
                "expires_at": time.time() + data.get("expires_in", 3600) - 60,
            }
            _save_token()
            return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


async def _refresh_token() -> bool:
    """Refresh the access token."""
    global _token_cache
    refresh = _token_cache.get("refresh_token")
    if not refresh:
        return False

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(TOKEN_URL, data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            })
            if resp.status_code == 200:
                data = resp.json()
                _token_cache["access_token"] = data["access_token"]
                if data.get("refresh_token"):
                    _token_cache["refresh_token"] = data["refresh_token"]
                _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600) - 60
                _save_token()
                return True
    except Exception as e:
        print(f"[Google] Refresh failed: {e}")
    return False


async def _get_token() -> str | None:
    """Get a valid access token, refreshing if needed."""
    _load_token()
    token = _token_cache.get("access_token")

    if _token_cache.get("expires_at", 0) < time.time():
        if _token_cache.get("refresh_token"):
            if await _refresh_token():
                return _token_cache["access_token"]
        if token:
            return token  # Try anyway, might still work
        return None

    return token


async def _api(url: str, params: dict = None) -> dict | None:
    """Make an authenticated Google API call."""
    token = await _get_token()
    if not token:
        return {"error": "not_authenticated", "auth_url": get_auth_url(),
                "message": "Connect your Google account to use this widget"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)

            if resp.status_code == 401:
                if await _refresh_token():
                    resp = await client.get(url,
                                            headers={"Authorization": f"Bearer {_token_cache['access_token']}"},
                                            params=params)
                else:
                    return {"error": "auth_expired", "auth_url": get_auth_url()}

            if resp.status_code != 200:
                return {"error": f"API returned {resp.status_code}: {resp.text[:200]}"}

            return resp.json()
    except Exception as e:
        return {"error": str(e)}


def is_authenticated() -> bool:
    """Check if we have a stored token."""
    _load_token()
    return bool(_token_cache.get("access_token"))


# ─── Google Calendar ───────────────────────────────────────────

async def get_next_meetings(count: int = 5) -> dict:
    """Fetch upcoming calendar events."""
    now = datetime.now(timezone.utc).isoformat()
    time_max = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    data = await _api(f"{CALENDAR_API}/calendars/primary/events", {
        "timeMin": now,
        "timeMax": time_max,
        "maxResults": count,
        "singleEvents": "true",
        "orderBy": "startTime",
    })

    if not data or data.get("error"):
        return data or {"error": "No response"}

    events = data.get("items", [])
    meetings = []

    for event in events:
        start = event.get("start", {})
        start_time = start.get("dateTime", start.get("date", ""))

        # Format time nicely
        try:
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            formatted = dt.strftime("%a %b %d, %I:%M %p")
        except Exception:
            formatted = start_time

        meeting = {
            "subject": event.get("summary", "No Title"),
            "start": formatted,
            "start_raw": start_time,
            "organizer": event.get("organizer", {}).get("email", "Unknown"),
            "attendees": len(event.get("attendees", [])),
            "join_url": event.get("hangoutLink", ""),
            "location": event.get("location", ""),
            "description": (event.get("description", "") or "")[:100],
        }
        meetings.append(meeting)

    return {
        "meetings": meetings,
        "count": len(meetings),
        "type": "calendar",
    }


# ─── Gmail ─────────────────────────────────────────────────────

async def get_unread_emails(count: int = 5, sender: str = None) -> dict:
    """Fetch recent unread emails from Gmail."""
    q = "is:unread"
    if sender:
        q += f" from:{sender}"
    data = await _api(f"{GMAIL_API}/users/me/messages", {
        "maxResults": count,
        "q": q,
    })

    if not data or data.get("error"):
        return data or {"error": "No response"}

    messages = data.get("messages", [])
    if not messages:
        return {"emails": [], "count": 0, "type": "gmail", "message": "Inbox zero! 🎉"}

    emails = []
    token = await _get_token()

    async with httpx.AsyncClient(timeout=15.0) as client:
        for msg in messages[:count]:
            try:
                resp = await client.get(
                    f"{GMAIL_API}/users/me/messages/{msg['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"format": "metadata", "metadataHeaders": "From,Subject,Date"},
                )
                if resp.status_code != 200:
                    continue

                email_data = resp.json()
                headers = email_data.get("payload", {}).get("headers", [])

                def _header(name):
                    return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")

                raw_sender = _header("From")
                # Extract name from "Name <email>" format
                if "<" in raw_sender:
                    sender_name = raw_sender.split("<")[0].strip().strip('"')
                    sender_email = raw_sender.split("<")[1].rstrip(">")
                else:
                    sender_name = raw_sender
                    sender_email = raw_sender

                emails.append({
                    "id": msg["id"],
                    "from_name": sender_name,
                    "from_email": sender_email,
                    "subject": _header("Subject") or "(No Subject)",
                    "date": _header("Date"),
                    "snippet": email_data.get("snippet", "")[:120],
                    "thread_id": email_data.get("threadId", ""),
                    "unread": True,
                })
            except Exception:
                continue

    title = f"Unread from {sender}" if sender else "Unread"
    return {
        "emails": emails,
        "count": len(emails),
        "type": "gmail",
        "title": f"{title} ({len(emails)})",
    }


async def get_latest_emails(count: int = 5, sender: str = None) -> dict:
    """Fetch latest emails (read or unread) from Gmail."""
    q = "in:inbox"
    if sender:
        q += f" from:{sender}"
    data = await _api(f"{GMAIL_API}/users/me/messages", {
        "maxResults": count,
        "q": q,
    })

    if not data or data.get("error"):
        return data or {"error": "No response"}

    messages = data.get("messages", [])
    if not messages:
        msg = f"No emails from {sender}" if sender else "No emails found"
        return {"emails": [], "count": 0, "type": "gmail_latest", "message": msg}

    emails = []
    token = await _get_token()

    async with httpx.AsyncClient(timeout=15.0) as client:
        for msg_item in messages[:count]:
            try:
                resp = await client.get(
                    f"{GMAIL_API}/users/me/messages/{msg_item['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"format": "metadata", "metadataHeaders": "From,Subject,Date"},
                )
                if resp.status_code != 200:
                    continue

                email_data = resp.json()
                headers = email_data.get("payload", {}).get("headers", [])

                def _header(name):
                    return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")

                raw_sender = _header("From")
                if "<" in raw_sender:
                    sender_name = raw_sender.split("<")[0].strip().strip('"')
                    sender_email = raw_sender.split("<")[1].rstrip(">")
                else:
                    sender_name = raw_sender
                    sender_email = raw_sender

                label_ids = email_data.get("labelIds", [])
                emails.append({
                    "id": msg_item["id"],
                    "from_name": sender_name,
                    "from_email": sender_email,
                    "subject": _header("Subject") or "(No Subject)",
                    "date": _header("Date"),
                    "snippet": email_data.get("snippet", "")[:120],
                    "thread_id": email_data.get("threadId", ""),
                    "unread": "UNREAD" in label_ids,
                })
            except Exception:
                continue

    title = f"Emails from {sender}" if sender else "Latest Emails"
    return {
        "emails": emails,
        "count": len(emails),
        "type": "gmail_latest",
        "title": title,
    }


async def get_email_summary() -> dict:
    """Get a quick summary of inbox status."""
    # Get unread count
    data = await _api(f"{GMAIL_API}/users/me/labels/INBOX")

    if not data or data.get("error"):
        return data or {"error": "No response"}

    unread = data.get("messagesUnread", 0)
    total = data.get("messagesTotal", 0)

    # Get latest unread emails
    emails_data = await get_unread_emails(3)

    return {
        "unread_count": unread,
        "total_count": total,
        "latest_emails": emails_data.get("emails", []),
        "type": "gmail_summary",
    }


# ─── YouTube search ───────────────────────────────────────────

async def search_youtube(query: str = "music", count: int = 5) -> dict:
    """Search YouTube via Data API v3 using the OAuth token."""
    token = await _get_token()
    if not token:
        return {
            "error": "not_authenticated",
            "auth_url": get_auth_url(),
            "message": "Connect your Google account to search YouTube",
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{YOUTUBE_API}/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": str(min(count, 10)),
                    "order": "relevance",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            data = r.json()

        videos = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            vid = item.get("id", {}).get("videoId", "")
            videos.append({
                "video_id": vid,
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "published": snippet.get("publishedAt", "")[:10],
                "url": f"https://www.youtube.com/watch?v={vid}",
            })

        return {
            "videos": videos,
            "query": query,
            "count": len(videos),
            "type": "youtube",
        }
    except httpx.HTTPStatusError as e:
        err_body = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
        err_msg = err_body.get("error", {}).get("message", str(e))
        if "insufficientPermissions" in str(err_body) or e.response.status_code == 403:
            return {
                "error": "scope_missing",
                "auth_url": get_auth_url(),
                "message": "YouTube access needs re-authorization. Please reconnect your Google account.",
            }
        return {"error": err_msg, "videos": []}
    except Exception as e:
        return {"error": str(e), "videos": []}


# ─── Google data entry point ──────────────────────────────────

async def get_google_data(data_type: str = "calendar", **kwargs) -> dict:
    """Main entry point for Google widgets."""
    _load_token()

    if not _token_cache.get("access_token"):
        return {
            "error": "not_authenticated",
            "auth_url": get_auth_url(),
            "message": "Connect your Google account to use this widget",
        }

    if data_type in ("meetings", "calendar"):
        count = kwargs.get("count", 5)
        return await get_next_meetings(count)
    elif data_type == "gmail":
        count = kwargs.get("count", 5)
        sender = kwargs.get("sender")
        return await get_unread_emails(count, sender=sender)
    elif data_type == "gmail_latest":
        count = kwargs.get("count", 5)
        sender = kwargs.get("sender")
        return await get_latest_emails(count, sender=sender)
    elif data_type == "gmail_summary":
        return await get_email_summary()
    elif data_type in ("youtube", "youtube_search"):
        query = kwargs.get("query", "music")
        count = kwargs.get("count", 5)
        return await search_youtube(query, count)
    else:
        return await get_next_meetings()


# Init on import
_load_token()
