import json
import hashlib
import re
import httpx
from backend.config import settings

# API endpoints
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
OLLAMA_CHAT_URL = f"{settings.OLLAMA_ENDPOINT}/api/chat"

# Simple in-memory cache for parsed intents
_intent_cache = {}

# Quick keyword patterns - ONLY for simple generic requests
# If prompt contains specific filters (process names, apps), skip this and use LLM
QUICK_PATTERNS = {
    # System health - ONLY exact simple phrases
    r"^(show\s*)?(my\s*)?(system\s*health|system\s*status|health\s*status)$": {
        "data_source": "system",
        "data_type": "health",
        "title": "System Health",
        "metrics": ["cpu", "ram", "disk", "battery"],
        "grouping": None,
        "count": None,
        "refresh_minutes": 1,
        "layout": "summary"
    },
    # GitHub activity - simple phrases only
    r"^(show\s*)?(my\s*)?(github\s*activity)$": {
        "data_source": "github",
        "data_type": "activity",
        "title": "GitHub Activity",
        "metrics": ["commits", "prs"],
        "grouping": None,
        "count": None,
        "refresh_minutes": 10,
        "layout": "summary"
    },
    # GitHub commits - simple
    r"^(show\s*)?(my\s*)?(commits?\s*today|today'?s?\s*commits?)$": {
        "data_source": "github",
        "data_type": "commits",
        "title": "Today's Commits",
        "metrics": ["total", "repos"],
        "grouping": "repo",
        "count": None,
        "refresh_minutes": 10,
        "layout": "summary"
    },
    # Standup - simple
    r"^(show\s*)?(my\s*)?(standup|standup\s*prep)$": {
        "data_source": "github",
        "data_type": "standup",
        "title": "Standup Prep",
        "metrics": ["commits", "prs"],
        "grouping": None,
        "count": None,
        "refresh_minutes": 30,
        "layout": "list"
    },
    # Hacker News / News - expanded
    r"^(show\s*)?(me\s*)?(hacker\s*news|hn|tech\s*news|latest\s*news|top\s*news|news\s*feed|world\s*news|headlines?)$": {
        "data_source": "news",
        "data_type": "latest",
        "title": "Latest News",
        "metrics": ["title", "source"],
        "grouping": None,
        "count": 8,
        "refresh_minutes": 15,
        "layout": "list"
    },
}


def _try_smart_pattern(prompt: str) -> dict | None:
    """Smart pattern matching for custom widget types."""
    prompt_lower = prompt.lower().strip()

    # ── Battery ──
    if re.search(r"\b(battery|charging|power\s*mode|drain|charge\s*cycle|battery\s*health)\b", prompt_lower):
        return {
            "data_source": "system", "data_type": "battery",
            "title": "Battery Health",
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 1, "layout": "summary"
        }

    # ── Clipboard History ──
    if re.search(r"\b(clipboard|copied|copy\s*history|paste\s*history|clip\s*history)\b", prompt_lower):
        return {
            "data_source": "system", "data_type": "clipboard",
            "title": "Clipboard History",
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "clipboard"
        }

    # ── My Day Dashboard ──
    if re.search(r"\b(my\s*day|daily\s*dashboard|morning\s*brief|day\s*overview|today.?s\s*(?:plan|summary|overview|agenda)|daily\s*agenda|daily\s*brief)\b", prompt_lower):
        return {
            "data_source": "composite", "data_type": "my_day",
            "title": "My Day",
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 5, "layout": "summary"
        }

    # ── Disk Space ──
    if re.search(r"\b(disk\s*space|storage|drive\s*usage|free\s*space|disk\s*usage|cleanup|clean\s*up|temp\s*files|recycle\s*bin)\b", prompt_lower):
        return {
            "data_source": "system", "data_type": "disk_space",
            "title": "Disk Space",
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 10, "layout": "summary"
        }

    # ── Network Monitor ──
    if re.search(r"\b(network|internet|wifi|wi-fi|speed\s*test|ping|bandwidth|connectivity|net\s*speed|upload|download\s*speed)\b", prompt_lower):
        return {
            "data_source": "system", "data_type": "network",
            "title": "Network Monitor",
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "summary"
        }

    # ── News (topic/category/crypto/market) ──
    if re.search(r"\b(news|headlines?|article|trending|current\s*events|whats\s*happening)\b", prompt_lower):
        # Detect special endpoints
        endpoint = "latest"
        if re.search(r"\b(crypto|bitcoin|blockchain|ethereum|web3)\b", prompt_lower):
            endpoint = "crypto"
        elif re.search(r"\b(market|stock\s*market|finance|financial|wall\s*street|sensex|nifty)\b", prompt_lower):
            endpoint = "market"

        # ── Extract topic FIRST (before category steals keywords) ──
        # Look for explicit topic patterns: "news about X", "news from X", "news on X"
        topic = None
        topic_match = re.search(
            r"(?:news|headlines?|articles?)\s+(?:about|from|on|regarding|of)\s+(.+?)$",
            prompt_lower
        )
        if topic_match:
            topic = topic_match.group(1).strip()
        else:
            # Try reverse: "X news" — but only if X has 2+ meaningful words
            # (single words like "tech", "crypto", "sports" should be categories, not topics)
            topic_match = re.search(
                r"^(?:show\s+)?(?:me\s+)?(?:latest\s+|recent\s+)?(.+?)\s+(?:news|headlines?|articles?)",
                prompt_lower
            )
            if topic_match:
                candidate = topic_match.group(1).strip()
                filler = {"show", "me", "the", "latest", "recent", "some", "all", "top", "get", "give"}
                words = [w for w in candidate.split() if w not in filler]
                # Category/endpoint single words should NOT be treated as topics
                single_word_cats = {
                    "tech", "technology", "sports", "sport", "business", "entertainment",
                    "science", "health", "politics", "world", "education", "environment",
                    "crypto", "bitcoin", "market", "finance", "financial",
                    "india", "indian", "us", "usa", "uk", "china", "japan", "australia",
                }
                if len(words) >= 2 or (len(words) == 1 and words[0] not in single_word_cats):
                    topic = " ".join(words)

        # Detect category (only if no specific topic was found)
        category = None
        if not topic:
            cat_map = {
                r"\b(tech|technology|software|gadget)\b": "technology",
                r"\b(sports?|football|soccer|tennis|f1|formula)\b": "sports",
                r"\b(business|economy|economic)\b": "business",
                r"\b(entertainment|movie|film|celebrity|bollywood|hollywood)\b": "entertainment",
                r"\b(science|space|nasa|research)\b": "science",
                r"\b(health|medical|covid|disease)\b": "health",
                r"\b(politic|election|government|minister|parliament)\b": "politics",
                r"\b(world|international|global)\b": "world",
                r"\b(education|school|university|college)\b": "education",
                r"\b(environment|climate|green|sustainability)\b": "environment",
            }
            for pat, cat in cat_map.items():
                if re.search(pat, prompt_lower):
                    category = cat
                    break

        # Detect country
        country = None
        country_map = {
            r"\b(india|indian|bharati?|desi)\b": "in",
            r"\b(us|usa|america|american|united states)\b": "us",
            r"\b(uk|britain|british|england)\b": "gb",
            r"\b(china|chinese)\b": "cn",
            r"\b(japan|japanese)\b": "jp",
            r"\b(australia|australian)\b": "au",
        }
        for pat, code in country_map.items():
            if re.search(pat, prompt_lower):
                country = code
                break

        # Build title
        if topic:
            title = f"News: {topic.title()}"
        elif endpoint == "crypto":
            title = "Crypto News"
        elif endpoint == "market":
            title = "Market News"
        elif category:
            title = f"{category.title()} News"
        else:
            title = "Latest News"

        result = {
            "data_source": "news", "data_type": endpoint,
            "title": title,
            "query": topic,  # pass topic directly as query
            "category": category if not topic else None,  # skip category filter when we have a specific topic
            "country": country,
            "metrics": [], "grouping": None, "count": 8,
            "refresh_minutes": 15, "layout": "list"
        }
        return result

    # ── Plane.so ──
    if re.search(r"\b(plane|plane\.so|plane\s*issues?|plane\s*tasks?|plane\s*work\s*items?)\b", prompt_lower):
        return {
            "data_source": "plane", "data_type": "issues",
            "title": "Plane Issues",
            "metrics": [], "grouping": None, "count": 10,
            "refresh_minutes": 5, "layout": "list"
        }

    # ── Google Search ──
    if re.search(r"\b(search|google|look\s*up|lookup|find\s+out|who\s+is|what\s+is|tell\s+me\s+about|info\s+on|information\s+about|define|meaning\s+of)\b", prompt_lower):
        return {
            "data_source": "search", "data_type": "web",
            "title": "Search",
            "query": "",  # filled by entity normalizer
            "needs_entity": True,
            "entity_type": "search_query",
            "metrics": [], "grouping": None, "count": 8,
            "refresh_minutes": 0, "layout": "search"
        }

    # ── YouTube / Music ──
    if re.search(r"\b(youtube|play|song|music|video|watch|listen)\b", prompt_lower):
        # Determine entity type: channel-specific or generic search?
        is_channel = bool(re.search(r"\b(channel|channels|creator|youtuber|uploads)\b", prompt_lower))
        return {
            "data_source": "google", "data_type": "youtube",
            "title": "YouTube",
            "query": "",  # filled by entity normalizer
            "needs_entity": True,
            "entity_type": "youtube_channel" if is_channel else "search_query",
            "metrics": [], "grouping": None, "count": 5,
            "refresh_minutes": 0, "layout": "youtube"
        }

    # ── Cricket ──
    if re.search(r"\b(cricket|ipl|t20|odi|test match|cricket schedule|live\s*(?:cricket\s*)?scores?|match\s*scores?)\b", prompt_lower):
        return {
            "data_source": "cricket", "data_type": "scores",
            "title": "Cricket Schedule",
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 5, "layout": "summary"
        }

    # ── Football / Soccer / Sports scores ──
    if re.search(r"\b(football|soccer|premier\s*league|la\s*liga|bundesliga|serie\s*a|champions\s*league|fifa|epl|live\s*(?:football|soccer|sports?)\s*scores?|(?:football|soccer)\s*scores?)\b", prompt_lower):
        return {
            "data_source": "news", "data_type": "stories",
            "title": "Football News & Scores",
            "metrics": [], "grouping": None, "count": 8,
            "refresh_minutes": 5, "layout": "list",
            "topic": "football",
            "category": "sports",
        }

    # ── Gmail ──
    if re.search(r"\b(gmail|emails?|inbox|unread|mails?)\b", prompt_lower):
        data_type = "gmail"
        title = "Gmail Inbox"
        count = 5
        needs_entity = False
        entity_type = None

        # Extract count
        count_match = re.search(r"\b(\d+)\s*(?:latest|recent|new|top|last)?", prompt_lower)
        if count_match:
            count = min(int(count_match.group(1)), 20)

        # Check if user wants emails from a specific sender
        has_sender = bool(re.search(r"(?:from|by)\s+[\w.@\-]+", prompt_lower))

        if re.search(r"\b(summary|overview|count)\b", prompt_lower):
            data_type = "gmail_summary"
            title = "Gmail Summary"
        elif re.search(r"\b(latest|recent|all|last|top|newest)\b", prompt_lower) or has_sender:
            data_type = "gmail_latest"
            title = "Latest Emails"
            if has_sender:
                needs_entity = True
                entity_type = "gmail_sender"
        elif re.search(r"\b(unread|new)\b", prompt_lower):
            title = "Unread Emails"

        result = {
            "data_source": "google", "data_type": data_type,
            "title": title,
            "metrics": [], "grouping": None, "count": count,
            "sender": None,
            "refresh_minutes": 2, "layout": "summary"
        }
        if needs_entity:
            result["needs_entity"] = True
            result["entity_type"] = entity_type
        return result

    # ── Google Calendar ──
    if re.search(r"\b(calendar|meetings?|schedules?|upcoming events?|my events?|google cal)\b", prompt_lower):
        return {
            "data_source": "google", "data_type": "calendar",
            "title": "Google Calendar",
            "metrics": [], "grouping": None, "count": 5,
            "refresh_minutes": 5, "layout": "summary"
        }

    # ── Timer / Clock detection ── (before URL check) ──
    timer_match = re.search(r"(?:timer|alarm|stopwatch)\s*(?:of|for|with)?\s*(\d+)\s*(sec|second|min|minute|hour|hr)?", prompt_lower)
    if timer_match or re.search(r"(\d+)\s*(sec|second|min|minute|hour|hr)\s*(?:timer|alarm|countdown)", prompt_lower):
        if not timer_match:
            timer_match = re.search(r"(\d+)\s*(sec|second|min|minute|hour|hr)", prompt_lower)
        if timer_match:
            val = int(timer_match.group(1))
            unit = timer_match.group(2) or "sec"
            if "min" in unit:
                seconds = val * 60
            elif "hour" in unit or "hr" in unit:
                seconds = val * 3600
            else:
                seconds = val
        else:
            seconds = 60
        return {
            "data_source": "custom", "data_type": "timer",
            "title": f"Timer ({seconds}s)" if seconds < 120 else f"Timer ({seconds//60}m)",
            "seconds": seconds, "initial_value": seconds,
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "summary"
        }
    
    # Simple "timer" or "clock" without number
    if re.search(r"\b(clock|time\s*widget)\b", prompt_lower):
        return {
            "data_source": "custom", "data_type": "clock",
            "title": "Clock",
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "summary"
        }
    
    if re.search(r"\btimer\b", prompt_lower) and not re.search(r"\d", prompt_lower):
        return {
            "data_source": "custom", "data_type": "timer",
            "title": "Timer (60s)",
            "seconds": 60, "initial_value": 60,
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "summary"
        }
    
    # ── URL / Link detection ──
    url_match = re.search(r'(https?://[^\s"\']+)', prompt)
    if url_match:
        url = url_match.group(1).rstrip('"\'')
        title = "Link Widget"
        if "youtube.com" in url or "youtu.be" in url:
            title = "YouTube Video"
        elif "github.com" in url:
            title = "GitHub Link"
        return {
            "data_source": "custom", "data_type": "link",
            "title": title, "url": url,
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "summary"
        }
    
    # ── Counter ──
    if re.search(r"\b(counter|counting|tally|increment)\b", prompt_lower):
        val_match = re.search(r"(?:start|from|at|value)\s*(\d+)", prompt_lower)
        return {
            "data_source": "custom", "data_type": "counter",
            "title": "Counter",
            "initial_value": int(val_match.group(1)) if val_match else 0,
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "summary"
        }
    
    # ── Checklist / Todo ──
    checklist_match = re.search(r"(?:checklist|todo|to-do|to do|shopping list|grocery list|task list)[:\s]*(.*)", prompt_lower)
    if checklist_match:
        items_str = checklist_match.group(1).strip()
        items = [i.strip().strip("-•*") .strip() for i in re.split(r'[,;\n]', items_str) if i.strip()]
        return {
            "data_source": "custom", "data_type": "checklist",
            "title": "Checklist",
            "items": items if items else ["Item 1", "Item 2", "Item 3"],
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "list"
        }
    
    # ── Note / Reminder ──
    note_match = re.search(r"(?:note|reminder|memo|sticky)[:\s]*(.*)", prompt_lower)
    if note_match:
        content = note_match.group(1).strip()
        return {
            "data_source": "custom", "data_type": "note",
            "title": "Note",
            "content": content or prompt,
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 0, "layout": "summary"
        }
    
    # ── Countdown ──
    countdown_match = re.search(r"(?:countdown|days?\s*(?:until|to|till)|deadline)[:\s]*(.*)", prompt_lower)
    if countdown_match:
        date_text = countdown_match.group(1).strip()
        # Try to parse a date
        target_date = None
        date_match = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", date_text)
        if date_match:
            target_date = date_match.group(1).replace("/", "-")
        else:
            # Try "March 15" style
            import calendar
            for i, month in enumerate(calendar.month_name):
                if month and month.lower() in date_text.lower():
                    day_match = re.search(r"(\d{1,2})", date_text)
                    day = int(day_match.group(1)) if day_match else 1
                    target_date = f"2026-{i:02d}-{day:02d}"
                    break
            for i, month in enumerate(calendar.month_abbr):
                if month and month.lower() in date_text.lower():
                    day_match = re.search(r"(\d{1,2})", date_text)
                    day = int(day_match.group(1)) if day_match else 1
                    target_date = f"2026-{i:02d}-{day:02d}"
                    break
        
        return {
            "data_source": "custom", "data_type": "countdown",
            "title": f"Countdown",
            "target_date": target_date or "2026-12-31",
            "metrics": [], "grouping": None, "count": None,
            "refresh_minutes": 60, "layout": "summary"
        }
    
    # ── Stock price ──\n    # Match: "stock/share/price/ticker X" or "track X stock" or "track TICKER"
    stock_match = re.search(r"(?:stock|share|price|ticker)[:\s]*(?:of\s+|for\s+)?(\w+)", prompt_lower)
    track_stock = re.search(r"\b(?:track|tracking)\s+([A-Z]{1,6})\b", prompt)  # "track TSLA" (uppercase ticker)
    track_named = re.search(r"\b(?:track|tracking)\s+\w+\s+stock", prompt_lower)  # "track tesla stock"
    if stock_match or track_stock or track_named:
        return {
            "data_source": "stock", "data_type": "price",
            "title": "Stock",
            "symbol": "",  # filled by entity normalizer
            "needs_entity": True,
            "entity_type": "stock_symbol",
            "metrics": ["price", "change"], "grouping": None, "count": None,
            "refresh_minutes": 5, "layout": "summary"
        }

    # ── Dynamic Plugin Matching ──────────────────────────────
    # Check if the prompt mentions any registered plugin widget by name,
    # id, or keywords. This lets dropped-in plugins be forge-able.
    try:
        from backend.services.widget_manifest import WIDGET_MANIFESTS
        for wid, manifest in WIDGET_MANIFESTS.items():
            # Skip built-in widgets (already handled above)
            builtin_ids = {"weather","news","search","cricket","google","github","ado","plane","system","custom","stock","composite"}
            if wid in builtin_ids:
                continue
            # Match against: widget name, id (with underscores as spaces), or keywords list
            name_lower = manifest.get("name", "").lower()
            id_as_words = wid.replace("_", " ")
            keywords = manifest.get("keywords", [])
            match_terms = [name_lower, id_as_words] + [k.lower() for k in keywords]
            for term in match_terms:
                if term and term in prompt_lower:
                    return {
                        "data_source": wid,
                        "data_type": "default",
                        "title": manifest.get("name", wid),
                        "metrics": [], "grouping": None, "count": None,
                        "refresh_minutes": manifest.get("runtime", {}).get("min_refresh_interval", 5),
                        "layout": "summary",
                    }
    except Exception:
        pass

    return None


def _try_quick_pattern(prompt: str) -> dict | None:
    """Try to match prompt against quick patterns (no LLM needed)."""
    prompt_lower = prompt.lower().strip()
    
    # First try smart patterns for custom types (URLs, counters, etc.)
    smart_result = _try_smart_pattern(prompt)
    if smart_result:
        return smart_result
    
    # Skip simple patterns if prompt contains specific filters
    specific_keywords = [
        r"\bof\s+\w+", r"\bfor\s+\w+", r"\bby\s+\w+",
        r"\bfilter", r"\bonly\b", r"\bprocess",
        r"\bapp\b", r"\bchrome\b", r"\bcode\b", r"\bvscode\b",
        r"\bpython\b", r"\bnode\b", r"\brunning\b",
    ]
    
    for skip_pattern in specific_keywords:
        if re.search(skip_pattern, prompt_lower):
            return None
    
    for pattern, intent in QUICK_PATTERNS.items():
        if re.search(pattern, prompt_lower, re.IGNORECASE):
            result = intent.copy()
            if result["data_source"] == "news":
                topic_match = re.search(r"about\s+(\w+)", prompt_lower)
                if topic_match:
                    result["topic"] = topic_match.group(1)
            return result
    return None


# ─── LLM Provider Implementations ─────────────────────────────

async def _call_groq(system_prompt: str, user_message: str) -> str:
    """Call Groq API (fastest cloud inference)."""
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GROQ_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def _call_gemini(system_prompt: str, user_message: str) -> str:
    """Call Google Gemini API."""
    url = f"{GEMINI_API_URL}/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_prompt}\n\nUser request: {user_message}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]


async def _call_ollama(system_prompt: str, user_message: str) -> str:
    """Call local Ollama API (slowest, but free and offline)."""
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(OLLAMA_CHAT_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["message"]["content"]


async def _call_llm(system_prompt: str, user_message: str) -> str:
    """Call the best available LLM provider with automatic fallback.
    
    Priority: Groq (fast) → Gemini (reliable) → Ollama (local)
    """
    provider = settings.LLM_PROVIDER.lower()
    
    # Determine provider order
    if provider == "groq":
        providers = [("groq", _call_groq)]
    elif provider == "gemini":
        providers = [("gemini", _call_gemini)]
    elif provider == "ollama":
        providers = [("ollama", _call_ollama)]
    else:  # "auto" - try all in order
        providers = []
        if settings.GROQ_API_KEY:
            providers.append(("groq", _call_groq))
        if settings.GEMINI_API_KEY:
            providers.append(("gemini", _call_gemini))
        providers.append(("ollama", _call_ollama))
    
    last_error = None
    for name, call_fn in providers:
        try:
            print(f"[LLM] Trying {name}...")
            result = await call_fn(system_prompt, user_message)
            print(f"[LLM] {name} succeeded")
            return result
        except Exception as e:
            print(f"[LLM] {name} failed: {e}")
            last_error = e
            continue
    
    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


# ─── Public API ────────────────────────────────────────────────

async def parse_intent(user_prompt: str, use_cache: bool = True) -> dict:
    """Parse natural language into structured widget intent.
    
    Uses three strategies for speed:
    1. Check cache for exact prompt match
    2. Try quick keyword patterns (instant, no LLM)
    3. Fall back to LLM (Groq/Gemini/Ollama) for complex prompts
    """
    # Strategy 1: Check cache
    cache_key = hashlib.md5(user_prompt.lower().strip().encode()).hexdigest()
    if use_cache and cache_key in _intent_cache:
        print(f"[LLM] Cache hit for: {user_prompt[:30]}...")
        return _intent_cache[cache_key]
    
    # Strategy 2: Try quick patterns (instant)
    quick_result = _try_quick_pattern(user_prompt)
    if quick_result:
        print(f"[LLM] Quick pattern match for: {user_prompt[:30]}...")
        _intent_cache[cache_key] = quick_result
        return quick_result
    
    # Strategy 3: Use LLM (Groq → Gemini → Ollama)
    print(f"[LLM] Calling LLM for: {user_prompt[:50]}...")
    with open("backend/prompts/intent_parser.txt") as f:
        system_prompt = f.read()

    content = await _call_llm(system_prompt, user_prompt)
    
    # Parse JSON from response
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            raise ValueError(f"Failed to parse LLM response: {content[:500]}")
    
    _intent_cache[cache_key] = result
    return result


async def generate_completion(system_prompt: str, user_message: str) -> str:
    """Generic LLM completion for other services."""
    return await _call_llm(system_prompt, user_message)
