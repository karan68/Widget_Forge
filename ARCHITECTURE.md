# Widget Forge — Technical Architecture

## System Overview

Widget Forge is a local-first, prompt-driven widget platform that demonstrates AI-first capabilities for the Windows Widget Board. This document covers the end-to-end technical architecture.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER LAYER                                │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │  Prompt Bar: "track TSLA stock"                          │     │
│  │  Suggestions Popup (✦ button + app scanning)             │     │
│  │  Widget Board (responsive grid, 3 sizes)                 │     │
│  └──────────────────────────────────────────────────────────┘     │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP (localhost:8000)
┌──────────────────────────────▼───────────────────────────────────┐
│                       PLATFORM LAYER                              │
│                                                                    │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│  │ Intent     │  │ Credential   │  │ Widget Manifest       │     │
│  │ Parser     │  │ Store        │  │ Registry              │     │
│  │            │  │              │  │                        │     │
│  │ - Rules    │  │ - Scoped     │  │ - 12 built-in         │     │
│  │ - Entities │  │ - File-based │  │ - Dynamic plugins     │     │
│  │ - LLM fb   │  │ - Masked     │  │ - Validation          │     │
│  └─────┬──────┘  └──────┬───────┘  └──────────┬────────────┘     │
│        │                │                      │                   │
│  ┌─────▼────────────────▼──────────────────────▼────────────┐     │
│  │                   Forge Pipeline                          │     │
│  │  parse_intent → check_state → fetch_data → gen_card       │     │
│  │       │              │             │            │          │     │
│  │    1ms rule      UNCONFIGURED?   connector   template     │     │
│  │    matching      → setup card    call        function     │     │
│  └──────────────────────┬───────────────────────────────────┘     │
│                         │                                          │
│  ┌──────────────────────▼───────────────────────────────────┐     │
│  │                  Lifecycle Engine                          │     │
│  │  UNCONFIGURED → CONFIGURED → ACTIVE → DEGRADED → DISABLED│     │
│  │  State persisted in widget_states.json                    │     │
│  │  Refresh gated by state. Failures transition state.       │     │
│  └──────────────────────────────────────────────────────────┘     │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                      CONNECTOR LAYER                              │
│                                                                    │
│  ┌────────┐ ┌────────┐ ┌─────────┐ ┌───────┐ ┌──────┐           │
│  │ GitHub │ │ News   │ │ Weather │ │ Stock │ │ ADO  │           │
│  │ API    │ │ API    │ │ API     │ │ API   │ │ API  │           │
│  └────────┘ └────────┘ └─────────┘ └───────┘ └──────┘           │
│  ┌────────┐ ┌────────┐ ┌─────────┐ ┌───────┐ ┌──────┐           │
│  │ Plane  │ │ Google │ │ Cricket │ │Search │ │System│           │
│  │ API    │ │ OAuth  │ │ API     │ │ API   │ │ Local│           │
│  └────────┘ └────────┘ └─────────┘ └───────┘ └──────┘           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Request Flow: Forge

```
User types: "show my Plane issues"
         │
         ▼
┌─ POST /api/widgets/forge ──────────────────────────────────────┐
│                                                                  │
│  1. parse_intent("show my Plane issues")                        │
│     → { data_source: "plane", data_type: "issues" }            │
│                                                                  │
│  2. check_widget_state("plane")                                 │
│     → Checks manifest capabilities                              │
│     → Checks credential store for PLANE_API_KEY                 │
│     → Result: { state: "unconfigured", missing: [Plane API] }  │
│                                                                  │
│  3. State == UNCONFIGURED                                       │
│     → credential_setup_card(state_info)                         │
│     → Returns Adaptive Card with:                               │
│       - "Why is this widget disabled?"                           │
│       - Step-by-step instructions to get API key                │
│       - Input fields for credentials                             │
│       - Save & Activate button                                   │
│     → widget.refresh_minutes = 0 (no auto-refresh)              │
│     → widget.widget_state = "unconfigured"                      │
│                                                                  │
│  4. User enters credentials → POST /api/widgets/credentials    │
│     → Validates keys against manifest (scoped access)           │
│     → Saves to credentials.json                                 │
│     → Tests with lightweight API call                            │
│     → Reloads into settings object                               │
│                                                                  │
│  5. Frontend re-forges with same prompt                         │
│     → check_widget_state("plane") → CONFIGURED                 │
│     → fetch_data(intent) → connector returns data               │
│     → plane_card(data) → Adaptive Card JSON                    │
│     → widget.widget_state = "active"                            │
│     → widget.refresh_minutes = 5 (from manifest)               │
│     → Auto-refresh starts in frontend                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Request Flow: Refresh

```
Auto-refresh tick (every N minutes)
         │
         ▼
┌─ Frontend: _scheduledRefresh(wid) ─────────────────────────────┐
│                                                                  │
│  1. _canRefresh(wid)?                                           │
│     → Is there a mutation in progress? (forge/delete) → skip    │
│     → Is this wid already in-flight? → skip                     │
│     → Is widget gone from DOM? → clear interval, skip           │
│                                                                  │
│  2. Add wid to inflight Set                                     │
│     → POST /api/widgets/refresh { widget_id: wid }             │
│                                                                  │
└─────────────────────┬──────────────────────────────────────────┘
                      │
                      ▼
┌─ Backend: refresh_widget(req) ─────────────────────────────────┐
│                                                                  │
│  1. Load widget from store                                      │
│  2. Check lifecycle state:                                      │
│     → DISABLED → return 409                                     │
│     → UNCONFIGURED → return 409                                 │
│     → DEGRADED → return 409                                     │
│     → ACTIVE/CONFIGURED → continue                              │
│                                                                  │
│  3. fetch_data(widget.intent) → connector call                  │
│  4. Check for errors:                                           │
│     → Error detected → state = DEGRADED, refresh_minutes = 0   │
│     → Success → state = ACTIVE                                  │
│  5. Regenerate Adaptive Card from template                      │
│  6. Persist state + return widget                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Intent Parser Architecture

```
Input: "track tesla stock"
         │
         ▼
┌─ Strategy 1: Cache ────────────────────────────────────────────┐
│  MD5 hash of prompt → check _intent_cache                       │
│  Cache hit → return immediately                                  │
└─────────────── miss ───────────────────────────────────────────┘
         │
         ▼
┌─ Strategy 2: Smart Patterns (_try_smart_pattern) ──────────────┐
│                                                                  │
│  30+ regex patterns checked in order:                           │
│  - Battery: \b(battery|charging|drain)\b                        │
│  - Clipboard: \b(clipboard|copied)\b                            │
│  - News: \b(news|headlines|trending)\b → sub-parse category     │
│  - Cricket: \b(cricket|ipl|t20)\b                               │
│  - Stock: \b(stock|share price|ticker)\b                        │
│  - Timer: timer\s*(\d+)\s*(min|sec)                             │
│  - ... etc                                                       │
│                                                                  │
│  Also checks: Dynamic Plugin Keywords                           │
│  → For each plugin in WIDGET_MANIFESTS (non-builtin):           │
│    → Match plugin name, id, or keywords[] against prompt        │
│    → Route to plugin's data_source                               │
│                                                                  │
│  Match → return structured intent (1ms)                          │
└─────────────── no match ───────────────────────────────────────┘
         │
         ▼
┌─ Strategy 3: Quick Patterns (QUICK_PATTERNS dict) ─────────────┐
│  Exact phrase matches for common prompts:                        │
│  - "system health" → system/health                               │
│  - "github activity" → github/activity                           │
│  - "hacker news" → news/latest                                   │
│                                                                  │
│  Skipped if prompt contains specific keywords (process names,   │
│  app names) that need LLM disambiguation                         │
└─────────────── no match ───────────────────────────────────────┘
         │
         ▼
┌─ Strategy 4: LLM (Groq → Gemini → Ollama) ────────────────────┐
│  System prompt with JSON schema                                  │
│  Groq (fastest): ~300ms                                          │
│  Gemini (fallback): ~500ms                                       │
│  Ollama (local fallback): ~1-2s                                  │
│  Returns structured JSON intent                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Credential Store Architecture

```
┌─ Credential Store (backend/store/credentials.json) ────────────┐
│                                                                  │
│  {                                                               │
│    "NEWSDATA_KEY": "pub_60bcfa...",                              │
│    "GITHUB_TOKEN": "ghp_xxxx...",                               │
│    "PLANE_API_KEY": "plane_api_xxxx..."                         │
│  }                                                               │
│                                                                  │
│  Access rules:                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ get_credential_for("github", "GITHUB_TOKEN")  → ✅ OK    │   │
│  │ get_credential_for("github", "NEWSDATA_KEY")  → ❌ NULL  │   │
│  │ get_credential_for("news",   "NEWSDATA_KEY")  → ✅ OK    │   │
│  │ get_credential_for("news",   "GITHUB_TOKEN")  → ❌ NULL  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Scoping enforced by:                                            │
│  1. get_credential_keys_for(data_source)                        │
│     → reads manifest capabilities → returns allowed keys         │
│  2. get_credential_for(data_source, key)                        │
│     → checks if key is in allowed set → returns value or null   │
│                                                                  │
│  Fallback chain:                                                 │
│  1. credentials.json (user-provided via UI)                     │
│  2. settings object (loaded from .env at startup)               │
│  3. os.environ (direct environment variable)                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌─ Widget State Store (backend/store/widget_states.json) ────────┐
│                                                                  │
│  {                                                               │
│    "a1b2c3d4": "active",                                        │
│    "e5f6g7h8": "degraded",                                      │
│    "i9j0k1l2": "disabled"                                       │
│  }                                                               │
│                                                                  │
│  Persisted across server restarts.                               │
│  Read by forge/refresh to gate execution.                        │
│  Written on every state transition.                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Manifest Validation Pipeline

```
Startup / Plugin Discovery
         │
         ▼
┌─ For each manifest ────────────────────────────────────────────┐
│                                                                  │
│  validate_manifest(manifest) → list[str]                        │
│                                                                  │
│  Checks:                                                         │
│  ├─ Required fields: id, name, version, description, category  │
│  ├─ id: must match ^[a-z][a-z0-9_]*$ (snake_case)             │
│  ├─ version: must match ^\d+\.\d+\.\d+$ (semver)              │
│  ├─ category: must be in VALID_CATEGORIES enum                  │
│  ├─ runtime section: required                                   │
│  │   ├─ refresh_policy: required (interval/manual/none)         │
│  │   └─ min_refresh_interval: must be >= 0                      │
│  ├─ failure section: required                                   │
│  │   └─ on_missing_credentials: required (block/fallback)       │
│  └─ capabilities[]:                                              │
│      ├─ service_name: required                                   │
│      ├─ type: must be api_key/oauth/pat/none                    │
│      ├─ required: flag required                                  │
│      ├─ scope: required for api_key/oauth/pat types             │
│      └─ setup_steps or setup_url: required when required=true   │
│                                                                  │
│  Errors → human-readable list                                    │
│  Empty list → manifest valid → registered in WIDGET_MANIFESTS   │
│  Non-empty → manifest rejected → logged to _discovery_errors    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Frontend Auto-Refresh System

```
┌─ _refreshState (singleton) ────────────────────────────────────┐
│                                                                  │
│  mutating: false          // true during forge/delete            │
│  inflight: Set()          // widget IDs currently refreshing     │
│  intervals: {}            // per-widget setInterval IDs          │
│                                                                  │
│  ┌─ _canRefresh(wid) ──────────────────────────────────────┐   │
│  │  return !mutating && !inflight.has(wid)                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ _startAutoRefresh(widget) ─────────────────────────────┐   │
│  │  Skip if:                                                │   │
│  │  - refresh_minutes <= 0                                  │   │
│  │  - widget_state == "unconfigured"                        │   │
│  │  - widget_state == "degraded"                            │   │
│  │  - widget_state == "disabled"                            │   │
│  │                                                          │   │
│  │  Otherwise: setInterval(_scheduledRefresh, ms)           │   │
│  │  Minimum interval: 10 seconds                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ forgeWidget() ─────────────────────────────────────────┐   │
│  │  mutating = true     // LOCK: block all refreshes       │   │
│  │  ... forge ...                                           │   │
│  │  mutating = false    // UNLOCK                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Plugin Discovery System

```
Server Startup
         │
         ▼
┌─ discover_plugins() ──────────────────────────────────────────┐
│                                                                  │
│  Scan: backend/widget_plugins/*/manifest.json                   │
│                                                                  │
│  For each folder:                                                │
│  ├─ No manifest.json? → log error, skip                        │
│  ├─ Invalid JSON? → log parse error, skip                       │
│  ├─ validate_manifest() fails? → log errors, skip              │
│  ├─ Duplicate id? → log conflict, skip                          │
│  └─ Valid? → add to WIDGET_MANIFESTS registry                   │
│                                                                  │
│  Result:                                                         │
│  [Plugins] Loaded 2 plugin widget(s): ['my_api_widget', ...]   │
│  [Plugins] WARNING: bad_widget → ['id must be snake_case', ...] │
│                                                                  │
│  Plugin widgets are then:                                        │
│  - Discoverable via /api/widgets/manifests                      │
│  - Forgeable via prompt (matched by name, id, or keywords)      │
│  - Credential-checked like built-in widgets                     │
│  - Auto-refreshed per manifest rules                             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

| Method | Path | Description | Auth State |
|---|---|---|---|
| `POST` | `/api/widgets/forge` | Natural language → live widget | Any |
| `POST` | `/api/widgets/refresh` | Re-fetch data for a widget | Blocks UNCONFIGURED, DEGRADED, DISABLED |
| `POST` | `/api/widgets/credentials` | Save API keys for a widget type | Any |
| `POST` | `/api/widgets/toggle` | Enable/disable a widget | Any |
| `POST` | `/api/widgets/reconfigure` | Clear credentials, show setup card | Requires credentials |
| `POST` | `/api/widgets/action` | Interactive actions (counter++, checklist toggle) | ACTIVE only |
| `GET` | `/api/widgets/list` | List all created widgets | Any |
| `GET` | `/api/widgets/manifests` | List all registered manifests with state | Any |
| `GET` | `/api/widgets/manifests/validate` | Validate all manifests, show errors | Any |
| `GET` | `/api/widgets/credentials` | List saved credentials (masked) | Any |
| `GET` | `/api/widgets/suggestions` | App-aware widget suggestions | Any |
| `GET` | `/api/widgets/types` | Widget types for Windows Widget Picker | Any |
| `GET` | `/api/widgets/card/{id}` | Raw Adaptive Card JSON for a widget | Any |
| `DELETE` | `/api/widgets/{id}` | Delete a widget | Any |
| `DELETE` | `/api/widgets/credentials/{key}` | Remove a specific credential | Any |
| `GET` | `/health` | Server health check | Any |

---

## Mapping to Windows Widget Platform

```
                    CURRENT                              WIDGET FORGE
                    ───────                              ────────────

Widget Host         WidgetBoard.exe                      Frontend (app.js)
                    (XAML + WebView2)                     (HTML + Adaptive Cards)
                         │                                    │
                         │ COM/RPC                            │ HTTP/REST
                         │                                    │
Widget Runtime      WidgetService.exe                    FastAPI Backend
                    (Singleton COM Server)                (widgets.py router)
                         │                                    │
                         │ COM activation                     │ Python import
                         │                                    │
Widget Provider     MSN Start Experiences App             Connectors
                    (C# / C++ packaged app                (github.py, news.py,
                     with IWidgetProvider)                  plane.py, etc.)
                         │                                    │
                         │ AppxManifest                       │ manifest.json
                         │ AppExtension                       │ widget_plugins/
                         │                                    │
Widget Catalog      WidgetCatalog API                    WIDGET_MANIFESTS dict
                    (enumerates installed                 (enumerates registered
                     widget providers)                    manifests + plugins)
                         │                                    │
                         │ Adaptive Card JSON                 │ Adaptive Card JSON
                         │ (returned by provider)             │ (returned by template)
                         ▼                                    ▼
                    ┌───────────────────────────────────────────┐
                    │        IDENTICAL OUTPUT FORMAT            │
                    │     Adaptive Card v1.5/1.6 JSON          │
                    │   Renderable by any Adaptive Card host   │
                    └───────────────────────────────────────────┘
```

---

## Test Coverage

```
43 tests across 7 categories:

TestManifestValidation (11 tests)
├── All built-in manifests valid
├── IDs are snake_case
├── Versions are semver
├── Categories are valid enum
├── Runtime section present
├── Failure section present
├── UI section present
├── Required capabilities have setup steps
├── Invalid manifest rejected (≥4 errors)
├── Invalid semver rejected
└── Invalid category rejected

TestLifecycleStateMachine (5 tests)
├── Widget state constants correct
├── UNCONFIGURED when credentials missing
├── No-credential widget is CONFIGURED
├── State persistence across save/load
└── DEGRADED → ACTIVE transition

TestCredentialAccess (6 tests)
├── Known widget has expected credential keys
├── Unknown widget returns empty set
├── Scoped access blocks wrong key
├── Scoped access allows own key
├── No-credential widget has empty keys
└── Plane manifest has expected fields

TestAutoRefreshRules (4 tests)
├── Manifest refresh intervals correct
├── Unknown widget gets default interval
├── Search is manual refresh
└── Custom is no refresh

TestFailureHandling (4 tests)
├── Credential-dependent widgets block on missing
├── No-credential widgets fallback on missing
├── Weather has fallback (wttr.in)
└── Rate limit policy exists for all

TestDynamicDiscovery (4 tests)
├── Plugins directory exists
├── discover_plugins returns list
├── Invalid plugin rejected with errors
└── Valid plugin loaded into registry

TestAPIEndpoints (9 tests)
├── Health endpoint
├── List manifests
├── Validate manifests endpoint
├── Forge system widget
├── Forge sets manifest refresh interval
├── Toggle widget (disable/enable)
├── Refresh blocked for DEGRADED widget
├── UNCONFIGURED widget shows setup card
└── Scope validation in capabilities
```
