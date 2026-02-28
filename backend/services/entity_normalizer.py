"""
Entity Normalization System
───────────────────────────
Deterministic entity extraction from noisy user prompts.

Pipeline:
  1. Intent detection marks `needs_entity` + `entity_type`
  2. Noise removal (global + entity-specific vocabularies)
  3. Candidate extraction (preserving token order & casing)
  4. 100-point confidence scoring
  5. LLM fallback only if confidence < 70
  6. Caching of resolved entities
"""

import re
import hashlib
from typing import Optional

# ─── Global Noise Vocabulary ──────────────────────────────────
# Tokens that can NEVER be part of an entity, across all types.

GLOBAL_NOISE = {
    # Verbs
    "show", "give", "add", "create", "make", "build", "generate", "get",
    "fetch", "track", "watch", "play", "listen", "search", "find",
    "display", "open", "load", "start", "set", "put", "run",
    # UI / Product terms
    "widget", "widgets", "dashboard", "card", "panel", "tile", "block",
    "view", "page", "screen", "app", "application",
    # Temporal / Recency
    "latest", "recent", "new", "always", "today", "now", "current",
    "ongoing", "live", "newest", "last", "first", "old", "older",
    # Prepositions / Connectors
    "with", "from", "of", "for", "by", "in", "on", "at", "to",
    "into", "about", "like", "than", "between", "through",
    # Generic modifiers
    "my", "me", "mine", "your", "user", "account", "profile",
    "i", "we", "you", "he", "she", "it", "they",
    # Auxiliary / filler
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would",
    "can", "could", "should", "shall", "may", "might", "must",
    "please", "want", "need", "want", "let", "just", "also",
    "and", "or", "but", "so", "if", "then", "not", "no", "yes",
    "all", "every", "each", "any", "some", "this", "that", "these",
    "those", "here", "there", "up", "down",
}


# ─── Entity-Specific Noise Vocabularies ───────────────────────

ENTITY_NOISE = {
    "youtube_channel": {
        "youtube", "yt", "channel", "channels", "video", "videos",
        "shorts", "reel", "reels", "subscribe", "subscription",
        "uploads", "content", "stream", "streaming", "vlog", "vlogs",
        "playlist", "playlists", "creator", "youtuber",
        "song", "songs", "music", "album", "beat", "beats",
    },
    "github_user": {
        "github", "gh", "user", "users", "profile", "account",
        "contributor", "maintainer", "developer", "commits",
        "prs", "pull", "issues", "repos", "repositories",
        "activity", "stats", "overview",
    },
    "github_repo": {
        "github", "repo", "repository", "project", "code", "source",
        "commits", "issues", "prs", "pull", "requests", "fork",
        "star", "stars", "clone", "track", "tracking",
    },
    "gmail_sender": {
        "gmail", "email", "emails", "mail", "mails", "inbox",
        "unread", "new", "latest", "message", "messages",
        "sender", "from", "sent", "received",
    },
    "stock_symbol": {
        "stock", "stocks", "share", "shares", "price", "value",
        "ticker", "market", "trading", "trade", "invest",
        "investment", "portfolio", "equity", "nse", "bse", "nasdaq",
    },
    "person": {
        "person", "people", "guy", "man", "woman", "somebody",
        "creator", "founder", "ceo", "youtuber", "developer",
        "engineer", "artist", "singer", "actor",
        "videos", "video", "news", "updates", "posts",
        "channel", "content", "stream",
    },
    "organization": {
        "company", "org", "organization", "firm", "startup",
        "enterprise", "team", "group", "corporation", "inc",
        "ltd", "llc",
        "news", "updates", "posts",
    },
    "search_query": {
        # For search/YouTube queries — strip platform/trigger words
        "youtube", "yt", "video", "videos",
        "search", "google", "lookup", "look",
        "define", "meaning", "info", "information",
        "tell", "who", "what", "when", "where", "how", "why",
    },
}

# ─── Known Entity Maps (for instant resolution) ──────────────

STOCK_NAME_MAP = {
    "adobe": "ADBE", "apple": "AAPL", "microsoft": "MSFT",
    "google": "GOOGL", "alphabet": "GOOGL", "amazon": "AMZN",
    "tesla": "TSLA", "meta": "META", "facebook": "META",
    "netflix": "NFLX", "nvidia": "NVDA", "amd": "AMD",
    "intel": "INTC", "disney": "DIS", "spotify": "SPOT",
    "amazon": "AMZN", "paypal": "PYPL", "uber": "UBER",
    "airbnb": "ABNB", "snapchat": "SNAP", "snap": "SNAP",
    "twitter": "TWTR", "x": "TWTR", "salesforce": "CRM",
    "oracle": "ORCL", "ibm": "IBM", "cisco": "CSCO",
    "qualcomm": "QCOM", "broadcom": "AVGO",
    "reliance": "RELIANCE.NS", "tata": "TCS.NS", "infosys": "INFY",
    "wipro": "WIPRO.NS", "hdfc": "HDFCBANK.NS",
}


# ─── Entity Cache ─────────────────────────────────────────────

_entity_cache: dict[str, str] = {}


def _cache_key(prompt: str, entity_type: str) -> str:
    normalized = prompt.lower().strip()
    return hashlib.md5(f"{entity_type}:{normalized}".encode()).hexdigest()


# ─── Core: Candidate Extraction ──────────────────────────────

def _extract_candidate(prompt: str, entity_type: str) -> str:
    """
    Remove global + entity-specific noise tokens.
    Preserve token order and capitalization signals from original prompt.
    """
    # Special case: email addresses — extract directly
    if entity_type == "gmail_sender":
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", prompt)
        if email_match:
            return email_match.group(0)

    noise = GLOBAL_NOISE | ENTITY_NOISE.get(entity_type, set())

    # Work on original prompt (preserve casing) but match noise case-insensitively
    tokens = prompt.split()
    filtered = [t for t in tokens if t.lower().strip(".,!?:;'\"") not in noise]

    # Strip leftover punctuation (but preserve / for repos and @ for emails and - for usernames)
    if entity_type in ("github_repo",):
        cleaned = [re.sub(r"^[^\w/]+|[^\w/]+$", "", t) for t in filtered]
    elif entity_type in ("github_user",):
        cleaned = [re.sub(r"^[^\w-]+|[^\w-]+$", "", t) for t in filtered]
    else:
        cleaned = [re.sub(r"^[^\w]+|[^\w]+$", "", t) for t in filtered]
    cleaned = [t for t in cleaned if t]  # drop empties

    return " ".join(cleaned)


# ─── Core: 100-Point Confidence Scoring ──────────────────────

def _score_entity(candidate: str, entity_type: str) -> int:
    """
    Score extracted entity on a 100-point scale.

    A. Structural Quality  (40 pts)
    B. Lexical Quality     (30 pts)
    C. Entity-Type Validity(20 pts)
    D. Ambiguity Penalty   (−20 to 0)
    """
    if not candidate or not candidate.strip():
        return 0

    tokens = candidate.split()
    score = 0

    # Fast-path: email addresses always high confidence
    if entity_type == "gmail_sender" and "@" in candidate:
        return 90

    # ── A. Structural Quality (40 pts) ──
    if len(tokens) >= 2:
        score += 20                                     # multi-token entity
    entity_len = len(candidate)
    if 2 <= entity_len <= 40:
        score += 10                                     # reasonable length
    # Token order is always preserved by design
    score += 10                                         # order preserved

    # ── B. Lexical Quality (30 pts) ──
    title_tokens = sum(1 for t in tokens if t[0].isupper())
    has_special = any("-" in t or "/" in t for t in tokens)  # github usernames/repos
    if title_tokens >= 1 or has_special:
        score += 15                                     # Title/CamelCase or special format
    if not any(t.lower() in GLOBAL_NOISE for t in tokens):
        score += 10                                     # no global noise leakage
    if not re.search(r"[^\w\s\-.'&@/]", candidate):
        score += 5                                      # no unexpected symbols

    # ── C. Entity-Type Validity (20 pts) ──
    ent_noise = ENTITY_NOISE.get(entity_type, set())
    pattern_ok = _matches_allowed_pattern(candidate, entity_type)
    if pattern_ok:
        score += 10                                     # matches allowed pattern
    if not any(t.lower() in ent_noise for t in tokens):
        score += 10                                     # no entity-specific noise

    # ── D. Ambiguity Penalty (−20 to 0) ──
    penalty = 0
    if len(tokens) == 1:
        # Single-word search queries and github users are fine
        if entity_type in ("search_query", "github_user", "github_repo"):
            pass  # no penalty
        elif tokens[0].lower() in _COMMON_WORDS:
            penalty -= 20
        elif tokens[0].islower():
            penalty -= 10
    if re.search(r"\d", candidate) and entity_type not in ("stock_symbol", "github_repo"):
        penalty -= 5
    penalty = max(penalty, -20)
    score += penalty

    return max(score, 0)


def _matches_allowed_pattern(candidate: str, entity_type: str) -> bool:
    """Check if candidate matches the expected shape for this entity type."""
    tokens = candidate.split()
    if entity_type == "youtube_channel":
        # 1-4 tokens, proper-noun-ish
        return 1 <= len(tokens) <= 4
    elif entity_type == "github_user":
        # alphanumeric + hyphens, single token usually
        return bool(re.match(r"^[\w\-]+$", candidate))
    elif entity_type == "github_repo":
        # owner/repo or single name, hyphens/underscores allowed
        return bool(re.match(r"^[\w\-]+(/[\w\-]+)?$", candidate))
    elif entity_type == "gmail_sender":
        # name or email address
        return len(tokens) <= 3 or "@" in candidate
    elif entity_type == "stock_symbol":
        # uppercase ticker (1-6 chars) or known company name
        if re.match(r"^[A-Z]{1,6}(\.\w+)?$", candidate):
            return True
        return candidate.lower() in STOCK_NAME_MAP
    elif entity_type == "person":
        return 1 <= len(tokens) <= 4
    elif entity_type == "organization":
        return 1 <= len(tokens) <= 5
    elif entity_type == "search_query":
        return len(candidate) >= 2
    return True


# Common dictionary words that are too ambiguous as single-token entities
_COMMON_WORDS = {
    "time", "day", "work", "home", "name", "data", "list", "help",
    "stuff", "thing", "things", "type", "kind", "sort", "way",
    "part", "place", "point", "end", "good", "bad", "big",
    "small", "long", "short", "high", "low", "old", "young",
    "plan", "idea", "test", "check", "update", "change", "top",
}


# ─── LLM Fallback (Entity-Only) ──────────────────────────────

async def _llm_extract_entity(prompt: str, entity_type: str) -> str | None:
    """
    Call LLM with a minimal prompt to extract ONLY the entity.
    Used only when confidence < 70.
    """
    from backend.services.llm_service import _call_llm
    import json

    type_descriptions = {
        "youtube_channel": "YouTube channel name",
        "github_user": "GitHub username",
        "github_repo": "GitHub repository name (owner/repo or just name)",
        "gmail_sender": "email sender (person name or email address)",
        "stock_symbol": "stock ticker symbol or company name",
        "person": "person's name",
        "organization": "organization/company name",
        "search_query": "search query/topic",
    }

    desc = type_descriptions.get(entity_type, entity_type)

    system = (
        "You are an entity extractor. From the user's prompt, extract ONLY the "
        f"{desc}. Return strict JSON: {{\"entity\": \"<extracted value>\"}}. "
        "If no entity found, return {\"entity\": \"\"}. "
        "Do NOT include filler words, commands, or platform names. "
        "Return ONLY the entity value."
    )

    try:
        raw = await _call_llm(system, prompt)
        data = json.loads(raw)
        entity = data.get("entity", "").strip()
        return entity if entity else None
    except Exception as e:
        print(f"[EntityNorm] LLM fallback failed: {e}")
        return None


# ─── Public API ───────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 70   # ≥70 accept, <70 LLM fallback

async def normalize_entity(
    prompt: str,
    entity_type: str,
    original_prompt: str | None = None,
) -> dict:
    """
    Main entry point. Returns:
      {
        "entity": str,          # the clean entity
        "confidence": int,      # 0-100
        "method": str,          # "deterministic" | "llm_fallback" | "cache"
      }
    """
    src_prompt = original_prompt or prompt
    ck = _cache_key(src_prompt, entity_type)

    # ── Step 0: Cache check ──
    if ck in _entity_cache:
        return {
            "entity": _entity_cache[ck],
            "confidence": 100,
            "method": "cache",
        }

    # ── Step 1: Stock symbol fast-path ──
    if entity_type == "stock_symbol":
        entity = _resolve_stock(prompt)
        if entity:
            _entity_cache[ck] = entity
            return {"entity": entity, "confidence": 95, "method": "deterministic"}

    # ── Step 2: Deterministic candidate extraction ──
    candidate = _extract_candidate(src_prompt, entity_type)
    confidence = _score_entity(candidate, entity_type)

    # ── Step 3: Confidence gate ──
    if confidence >= CONFIDENCE_THRESHOLD and candidate:
        # Normalize casing
        entity = _normalize_casing(candidate, entity_type)
        _entity_cache[ck] = entity
        return {
            "entity": entity,
            "confidence": confidence,
            "method": "deterministic",
        }

    # ── Step 4: LLM fallback ──
    print(f"[EntityNorm] Low confidence ({confidence}) for '{candidate}' "
          f"(type={entity_type}). Calling LLM fallback...")
    llm_entity = await _llm_extract_entity(src_prompt, entity_type)

    if llm_entity:
        final = _normalize_casing(llm_entity, entity_type)
        _entity_cache[ck] = final
        return {
            "entity": final,
            "confidence": 85,
            "method": "llm_fallback",
        }

    # ── Step 5: Last resort — use whatever we have ──
    fallback = candidate or prompt.strip()
    _entity_cache[ck] = fallback
    return {
        "entity": fallback,
        "confidence": max(confidence, 10),
        "method": "deterministic_low",
    }


def _normalize_casing(entity: str, entity_type: str) -> str:
    """Apply entity-type-appropriate casing."""
    if entity_type == "stock_symbol":
        mapped = STOCK_NAME_MAP.get(entity.lower())
        if mapped:
            return mapped
        if re.match(r"^[a-zA-Z]{1,6}(\. \w+)?$", entity):
            return entity.upper()
        return entity.title()
    elif entity_type in ("github_user", "github_repo"):
        return entity  # preserve original casing
    elif entity_type == "gmail_sender":
        # Preserve email addresses as-is (lowercase)
        if "@" in entity:
            return entity.lower()
        return entity.title() if entity.islower() else entity
    elif entity_type == "search_query":
        return entity.lower()
    else:
        return entity.title() if entity.islower() else entity


def _resolve_stock(prompt: str) -> str | None:
    """Fast-path: resolve known stock names to symbols."""
    prompt_lower = prompt.lower()
    for name, symbol in STOCK_NAME_MAP.items():
        if name in prompt_lower:
            return symbol
    # Check for raw ticker (e.g., "TSLA stock")
    ticker_match = re.search(r"\b([A-Z]{1,6})\b", prompt)
    if ticker_match:
        sym = ticker_match.group(1)
        if sym not in {"I", "A", "IT", "THE", "TO", "IN", "ON", "AT", "BY",
                        "OR", "AN", "IS", "IF", "MY", "ME", "UP", "DO", "NO",
                        "SO", "OF", "US", "AM", "AS", "BE", "HE", "WE"}:
            return sym
    return None


# ─── Convenience: normalize intent in-place ───────────────────

async def enrich_intent_with_entity(intent: dict, original_prompt: str) -> dict:
    """
    If the intent has `needs_entity: true`, run entity normalization
    and attach the result to the intent dict.
    """
    if not intent.get("needs_entity"):
        return intent

    entity_type = intent.get("entity_type", "search_query")
    result = await normalize_entity(
        prompt=original_prompt,
        entity_type=entity_type,
        original_prompt=original_prompt,
    )

    entity = result["entity"]

    # Attach to the appropriate intent field based on type
    if entity_type == "youtube_channel":
        intent["query"] = entity
        intent["title"] = f"YouTube: {entity}"
    elif entity_type == "search_query":
        intent["query"] = entity
        # Set title based on data source
        ds = intent.get("data_source", "")
        if ds == "search":
            intent["title"] = f"🔍 {entity.title()}"
        elif ds == "google":
            intent["title"] = f"YouTube: {entity.title()}"
        elif ds == "news":
            intent["title"] = f"News: {entity.title()}"
        else:
            intent["title"] = entity.title()
    elif entity_type in ("github_user", "github_repo"):
        intent["query"] = entity
    elif entity_type == "gmail_sender":
        intent["sender"] = entity
        intent["title"] = f"Emails from {entity}"
    elif entity_type == "stock_symbol":
        intent["symbol"] = entity
        intent["title"] = f"{entity} Stock"
    else:
        intent["query"] = entity

    # Attach normalization metadata
    intent["_entity"] = result
    # Remove the marker flags
    intent.pop("needs_entity", None)

    return intent
