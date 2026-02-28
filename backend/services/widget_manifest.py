"""
Widget Manifest Registry
────────────────────────
Declares what each widget type requires: credentials, OAuth, setup instructions.
This is the single source of truth for capability requirements.

Lifecycle states:
  UNCONFIGURED → CONFIGURED → ACTIVE → DEGRADED → DISABLED

A widget is UNCONFIGURED when required credentials are missing.
The platform gates execution — widgets never access credentials directly.

Dynamic Discovery:
  Place a manifest.json in  backend/widget_plugins/<widget_id>/manifest.json
  to register a new widget without modifying code or redeploying.
"""

import json
import re
from pathlib import Path

# ─── Category Enum ────────────────────────────────────────────

VALID_CATEGORIES = {
    "Essentials", "Media", "Utility", "Sports", "Google",
    "Dev", "Finance", "Fun", "Work", "Gaming", "Creative", "Web",
}

VALID_CAPABILITY_TYPES = {"api_key", "oauth", "pat", "none"}

# ─── Manifest Validation ─────────────────────────────────────

REQUIRED_MANIFEST_FIELDS = {"id", "name", "version", "description", "category"}

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_manifest(manifest: dict) -> list[str]:
    """
    Validate a widget manifest against the specification.
    Returns a list of human-readable error strings.  Empty list = valid.
    """
    errors: list[str] = []

    # Required fields
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest or not manifest[field]:
            errors.append(f"Missing required field: '{field}'")

    # ID: snake_case
    wid = manifest.get("id", "")
    if wid and not _SNAKE_RE.match(wid):
        errors.append(f"Widget id '{wid}' must be snake_case (lowercase + underscores)")

    # Version: semver
    ver = manifest.get("version", "")
    if ver and not _SEMVER_RE.match(ver):
        errors.append(f"Version '{ver}' must follow semver (e.g. 1.0.0)")

    # Category: enum
    cat = manifest.get("category", "")
    if cat and cat not in VALID_CATEGORIES:
        errors.append(f"Category '{cat}' must be one of: {sorted(VALID_CATEGORIES)}")

    # Runtime section
    runtime = manifest.get("runtime")
    if runtime is None:
        errors.append("Missing required section: 'runtime'")
    else:
        if "refresh_policy" not in runtime:
            errors.append("runtime.refresh_policy is required ('interval' | 'manual' | 'none')")
        mri = runtime.get("min_refresh_interval")
        if mri is not None and (not isinstance(mri, (int, float)) or mri < 0):
            errors.append(f"runtime.min_refresh_interval must be >= 0, got {mri}")

    # Failure section
    failure = manifest.get("failure")
    if failure is None:
        errors.append("Missing required section: 'failure'")
    else:
        if "on_missing_credentials" not in failure:
            errors.append("failure.on_missing_credentials is required ('block' | 'fallback')")

    # Capabilities
    caps = manifest.get("capabilities", [])
    for i, cap in enumerate(caps):
        if not cap.get("service_name"):
            errors.append(f"capabilities[{i}].service_name is required")
        ctype = cap.get("type", "")
        if ctype and ctype not in VALID_CAPABILITY_TYPES:
            errors.append(f"capabilities[{i}].type '{ctype}' must be one of {VALID_CAPABILITY_TYPES}")
        if "required" not in cap:
            errors.append(f"capabilities[{i}].required flag is required")
        if cap.get("required") and ctype in ("api_key", "oauth", "pat"):
            if not cap.get("setup_steps") and not cap.get("setup_url"):
                errors.append(f"capabilities[{i}] requires setup_steps or setup_url when required=True")
        # Scope is required for non-none capability types
        if ctype and ctype != "none" and not cap.get("scope"):
            errors.append(f"capabilities[{i}] must declare a 'scope' when type is '{ctype}'")

    return errors


# ─── Widget Capability Types ──────────────────────────────────
# Each capability declares:
#   service_name  : Human-readable name (e.g., "WeatherAPI.com")
#   type          : "api_key" | "oauth" | "pat" | "none"
#   required      : Whether the widget cannot function without this
#   config_key    : The key name in the credential store
#   env_fallback  : The env var to check as fallback (for backward compat)
#   setup_url     : URL where the user can get the credential
#   setup_steps   : Human-readable steps to obtain the credential
#   scope         : For OAuth, the scopes needed

WIDGET_MANIFESTS: dict[str, dict] = {
    # ─── Weather ──────────────────────────────────────────────
    "weather": {
        "id": "weather",
        "name": "Weather",
        "version": "1.0.0",
        "description": "Current weather with AQI, wind, humidity",
        "category": "Essentials",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 5, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "fallback", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "md", "icon": "🌦️"},
        "capabilities": [
            {
                "service_name": "WeatherAPI.com",
                "type": "api_key",
                "required": False,  # has wttr.in fallback
                "scope": "weather_data",
                "config_key": "WEATHERAPI_KEY",
                "env_fallback": "WEATHERAPI_KEY",
                "setup_url": "https://www.weatherapi.com/signup.aspx",
                "setup_steps": [
                    "Go to weatherapi.com and create a free account",
                    "Copy your API key from the dashboard",
                    "Paste it below",
                ],
                "placeholder": "e.g., df1d8a89de794eb9b07143839262702",
            }
        ],
    },

    # ─── News ─────────────────────────────────────────────────
    "news": {
        "id": "news",
        "name": "News",
        "version": "1.0.0",
        "description": "Latest news, crypto news, market news",
        "category": "Media",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 5, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "block", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "lg", "icon": "📰"},
        "capabilities": [
            {
                "service_name": "NewsData.io",
                "type": "api_key",
                "required": True,
                "scope": "news_read",
                "config_key": "NEWSDATA_KEY",
                "env_fallback": "NEWSDATA_KEY",
                "setup_url": "https://newsdata.io/register",
                "setup_steps": [
                    "Go to newsdata.io and create a free account",
                    "Go to API Keys in your dashboard",
                    "Copy the API key and paste it below",
                ],
                "placeholder": "e.g., pub_xxxxxxxxxxxxxxxxxxxxx",
            }
        ],
    },

    # ─── Search ───────────────────────────────────────────────
    "search": {
        "id": "search",
        "name": "Google Search",
        "version": "1.0.0",
        "description": "Web search results with knowledge graph",
        "category": "Utility",
        "runtime": {"refresh_policy": "manual", "min_refresh_interval": 1, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "block", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "lg", "icon": "🔍"},
        "capabilities": [
            {
                "service_name": "Serpstack",
                "type": "api_key",
                "required": True,
                "scope": "search_read",
                "config_key": "SERPSTACK_KEY",
                "env_fallback": "SERPSTACK_KEY",
                "setup_url": "https://serpstack.com/signup/free",
                "setup_steps": [
                    "Go to serpstack.com and create a free account",
                    "Copy your API Access Key from the dashboard",
                    "Paste it below",
                ],
                "placeholder": "e.g., 7c81aa401e511b6f9d...",
            }
        ],
    },

    # ─── Cricket ──────────────────────────────────────────────
    "cricket": {
        "id": "cricket",
        "name": "Cricket",
        "version": "1.0.0",
        "description": "Live scores and schedule",
        "category": "Sports",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 2, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "block", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "md", "icon": "🏏"},
        "capabilities": [
            {
                "service_name": "RapidAPI (Cricbuzz)",
                "type": "api_key",
                "required": True,
                "scope": "cricket_read",
                "config_key": "RAPIDAPI_KEY",
                "env_fallback": "RAPIDAPI_KEY",
                "setup_url": "https://rapidapi.com/hub",
                "setup_steps": [
                    "Go to rapidapi.com and create a free account",
                    "Subscribe to the free Cricbuzz Cricket API",
                    "Copy your X-RapidAPI-Key and paste it below",
                ],
                "placeholder": "e.g., a00d923f81msh...",
            }
        ],
    },

    # ─── Google (Calendar, Gmail, YouTube) ────────────────────
    "google": {
        "id": "google",
        "name": "Google Services",
        "version": "1.0.0",
        "description": "Calendar, Gmail, YouTube",
        "category": "Google",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 3, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "block", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "lg", "icon": "📧"},
        "capabilities": [
            {
                "service_name": "Google OAuth",
                "type": "oauth",
                "required": True,
                "scope": "calendar.readonly gmail.readonly youtube.readonly",
                "config_key": "GOOGLE_CLIENT_ID",
                "config_keys": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"],
                "env_fallback": "GOOGLE_CLIENT_ID",
                "setup_url": "https://console.cloud.google.com/apis/credentials",
                "setup_steps": [
                    "Go to Google Cloud Console → APIs & Services → Credentials",
                    "Create an OAuth 2.0 Client ID (Web Application)",
                    "Set redirect URI to http://localhost:8000/callback/google",
                    "Copy Client ID and Client Secret below",
                ],
                "fields": [
                    {"key": "GOOGLE_CLIENT_ID", "label": "Client ID", "placeholder": "xxxx.apps.googleusercontent.com"},
                    {"key": "GOOGLE_CLIENT_SECRET", "label": "Client Secret", "placeholder": "GOCSPX-..."},
                    {"key": "GOOGLE_REDIRECT_URI", "label": "Redirect URI", "placeholder": "http://localhost:8000/callback/google", "default": "http://localhost:8000/callback/google"},
                ],
            }
        ],
    },

    # ─── GitHub ───────────────────────────────────────────────
    "github": {
        "id": "github",
        "name": "GitHub",
        "version": "1.0.0",
        "description": "Commits, PRs, activity",
        "category": "Dev",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 5, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "block", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "lg", "icon": "🐙"},
        "capabilities": [
            {
                "service_name": "GitHub Personal Access Token",
                "type": "pat",
                "required": True,
                "scope": "repo,read:user",
                "config_key": "GITHUB_TOKEN",
                "env_fallback": "GITHUB_TOKEN",
                "setup_url": "https://github.com/settings/tokens",
                "setup_steps": [
                    "Go to GitHub → Settings → Developer settings → Personal access tokens",
                    "Generate a new token (classic) with 'repo' and 'read:user' scopes",
                    "Copy the token and paste it below",
                ],
                "fields": [
                    {"key": "GITHUB_TOKEN", "label": "Personal Access Token", "placeholder": "ghp_xxxxxxxxxxxx"},
                    {"key": "GITHUB_USERNAME", "label": "GitHub Username", "placeholder": "your-username"},
                ],
            }
        ],
    },

    # ─── ADO ──────────────────────────────────────────────────
    "ado": {
        "id": "ado",
        "name": "Azure DevOps",
        "version": "1.0.0",
        "description": "Work items, bugs, boards",
        "category": "Dev",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 5, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "block", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "lg", "icon": "🔷"},
        "capabilities": [
            {
                "service_name": "Azure DevOps PAT",
                "type": "pat",
                "required": True,
                "scope": "work_items.read",
                "config_key": "ADO_PAT",
                "env_fallback": "ADO_PAT",
                "setup_url": "https://dev.azure.com",
                "setup_steps": [
                    "Go to Azure DevOps → User Settings → Personal Access Tokens",
                    "Create a new token with 'Work Items: Read' scope",
                    "Copy your org URL, project name, and token below",
                ],
                "fields": [
                    {"key": "ADO_ORG", "label": "Organization URL", "placeholder": "https://dev.azure.com/your-org"},
                    {"key": "ADO_PROJECT", "label": "Project Name", "placeholder": "MyProject"},
                    {"key": "ADO_PAT", "label": "Personal Access Token", "placeholder": "xxxxxxxxxxxxxx"},
                ],
            }
        ],
    },

    # ─── Plane.so ─────────────────────────────────────────────
    "plane": {
        "id": "plane",
        "name": "Plane.so",
        "version": "1.0.0",
        "description": "Issues, cycles, modules from Plane",
        "category": "Dev",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 5, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "block", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "lg", "icon": "✈️"},
        "capabilities": [
            {
                "service_name": "Plane API",
                "type": "api_key",
                "required": True,
                "scope": "issues.read",
                "config_key": "PLANE_API_KEY",
                "env_fallback": "PLANE_API_KEY",
                "setup_url": "https://app.plane.so/settings",
                "setup_steps": [
                    "Log into Plane.so → Profile Settings",
                    "Go to Personal Access Tokens",
                    "Create a new token and copy it",
                    "Also provide your workspace slug (from URL)",
                ],
                "fields": [
                    {"key": "PLANE_API_KEY", "label": "API Key", "placeholder": "plane_api_xxxx"},
                    {"key": "PLANE_WORKSPACE", "label": "Workspace Slug", "placeholder": "my-workspace"},
                    {"key": "PLANE_BASE_URL", "label": "Base URL (optional)", "placeholder": "https://api.plane.so (not app.plane.so)", "default": "https://api.plane.so"},
                ],
            }
        ],
    },

    # ─── No-credential widgets ────────────────────────────────
    "system": {
        "id": "system",
        "name": "System Monitor",
        "version": "1.0.0",
        "description": "CPU, RAM, battery, disk, network",
        "category": "Essentials",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 1, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "fallback", "on_rate_limit": "ignore", "on_timeout": "retry"},
        "ui": {"default_size": "md", "icon": "💻"},
        "capabilities": [],
    },
    "custom": {
        "id": "custom",
        "name": "Custom Widgets",
        "version": "1.0.0",
        "description": "Counter, timer, clock, checklist, notes",
        "category": "Essentials",
        "runtime": {"refresh_policy": "none", "min_refresh_interval": 0, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "fallback", "on_rate_limit": "ignore", "on_timeout": "ignore"},
        "ui": {"default_size": "sm", "icon": "🧩"},
        "capabilities": [],
    },
    "stock": {
        "id": "stock",
        "name": "Stock Tracker",
        "version": "1.0.0",
        "description": "Real-time stock prices",
        "category": "Finance",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 3, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "fallback", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "md", "icon": "📈"},
        "capabilities": [],
    },
    "composite": {
        "id": "composite",
        "name": "Dashboard",
        "version": "1.0.0",
        "description": "Combined widgets (My Day)",
        "category": "Essentials",
        "runtime": {"refresh_policy": "interval", "min_refresh_interval": 5, "concurrent_requests": False},
        "failure": {"on_missing_credentials": "fallback", "on_rate_limit": "degrade", "on_timeout": "retry"},
        "ui": {"default_size": "lg", "icon": "📊"},
        "capabilities": [],
    },
}


# ─── Lifecycle States ────────────────────────────────────────

class WidgetState:
    UNCONFIGURED = "unconfigured"   # missing required credentials
    CONFIGURED   = "configured"     # credentials present, not yet fetched
    ACTIVE       = "active"         # data fetched successfully
    DEGRADED     = "degraded"       # API error, rate limit, etc.
    DISABLED     = "disabled"       # explicitly disabled by user


# ─── Dynamic Widget Discovery ────────────────────────────────
# Scan  backend/widget_plugins/<id>/manifest.json  at startup.

PLUGINS_DIR = Path("backend/widget_plugins")
_discovery_errors: list[dict] = []


def discover_plugins() -> list[dict]:
    """
    Scan the plugins directory for widget manifests.
    Valid manifests are merged into WIDGET_MANIFESTS.
    Invalid ones are logged in _discovery_errors.
    Returns list of successfully loaded manifests.
    """
    global _discovery_errors
    _discovery_errors = []
    loaded: list[dict] = []

    if not PLUGINS_DIR.exists():
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        return loaded

    for folder in sorted(PLUGINS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        manifest_file = folder / "manifest.json"
        if not manifest_file.exists():
            _discovery_errors.append({
                "path": str(folder),
                "errors": ["No manifest.json found in widget folder"],
            })
            continue
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as e:
            _discovery_errors.append({
                "path": str(manifest_file),
                "errors": [f"Failed to parse manifest.json: {e}"],
            })
            continue

        errors = validate_manifest(manifest)
        if errors:
            _discovery_errors.append({
                "path": str(manifest_file),
                "errors": errors,
            })
            continue

        wid = manifest["id"]
        if wid in WIDGET_MANIFESTS:
            _discovery_errors.append({
                "path": str(manifest_file),
                "errors": [f"Duplicate widget id '{wid}' — already registered"],
            })
            continue

        WIDGET_MANIFESTS[wid] = manifest
        loaded.append(manifest)

    return loaded


def get_discovery_errors() -> list[dict]:
    """Return errors from the last discovery run."""
    return list(_discovery_errors)


# ─── Public API ───────────────────────────────────────────────

def get_manifest(data_source: str) -> dict | None:
    """Get the manifest for a data source."""
    return WIDGET_MANIFESTS.get(data_source)


def get_required_capabilities(data_source: str) -> list[dict]:
    """Get the list of required capabilities for a data source."""
    manifest = get_manifest(data_source)
    if not manifest:
        return []
    return [c for c in manifest.get("capabilities", []) if c.get("required")]


def get_all_capabilities(data_source: str) -> list[dict]:
    """Get all capabilities (required + optional) for a data source."""
    manifest = get_manifest(data_source)
    if not manifest:
        return []
    return manifest.get("capabilities", [])


def get_credential_keys_for(data_source: str) -> set[str]:
    """Return the set of credential config_key values owned by a widget type."""
    manifest = get_manifest(data_source)
    if not manifest:
        return set()
    keys: set[str] = set()
    for cap in manifest.get("capabilities", []):
        if cap.get("fields"):
            for f in cap["fields"]:
                keys.add(f["key"])
        elif cap.get("config_keys"):
            keys.update(cap["config_keys"])
        elif cap.get("config_key"):
            keys.add(cap["config_key"])
    return keys


def get_refresh_interval(data_source: str) -> int:
    """Get the min_refresh_interval from the manifest (in minutes). 0 = no refresh."""
    manifest = get_manifest(data_source)
    if not manifest:
        return 5
    runtime = manifest.get("runtime", {})
    return runtime.get("min_refresh_interval", 5)


def list_all_manifests() -> list[dict]:
    """List all registered widget manifests."""
    return list(WIDGET_MANIFESTS.values())


def list_manifests_needing_credentials() -> list[dict]:
    """List manifests that require at least one credential."""
    return [m for m in WIDGET_MANIFESTS.values() if m.get("capabilities")]
