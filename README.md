# Widget Forge

**Type what you want. Get a live widget.**

Widget Forge is an AI-first, local-first widget platform that turns natural language prompts into live, self-configuring Adaptive Card widgets. Built as a hackathon POC to demonstrate capabilities missing from the Windows Widget Board — prompt-driven creation, credential lifecycle management, manifest-only extensibility, and structured failure recovery.

```
"track TSLA stock"         → live stock price widget (2 seconds)
"show my GitHub activity"  → commits, PRs, reviews dashboard
"show my Plane issues"     → credential setup card → enter API key → live widget
"5 min timer"              → interactive countdown timer
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **One LLM provider** (any one):
  - [Groq](https://console.groq.com/) API key (free, fastest)
  - [Google Gemini](https://aistudio.google.com/apikey) API key (free)
  - [Ollama](https://ollama.com/) running locally (no API key needed)

### Setup

```bash
# Clone
git clone https://github.com/karan68/Widget_Forge.git
cd Widget_Forge

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install fastapi uvicorn httpx pydantic python-dotenv psutil

# Configure environment
copy .env.example .env
# Edit .env and add at least one LLM API key (GROQ_API_KEY recommended)

# Run
uvicorn backend.main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

### Minimum .env for First Run

You only need **one LLM key** to start. Widget-specific API keys are entered via the UI when needed.

```env
GROQ_API_KEY=gsk_your_key_here
```

---

## What It Does

### Type a Prompt, Get a Widget

| Prompt | Widget | Credentials Needed |
|---|---|---|
| `show system health` | CPU, RAM, disk, battery stats | None |
| `clock widget` | Live clock with date | None |
| `5 min timer` | Interactive countdown | None |
| `checklist: standup, review PRs, deploy` | Interactive checklist | None |
| `track TSLA stock` | Live stock price | None |
| `weather in Hyderabad` | Temperature, humidity, wind | None (wttr.in fallback) |
| `show tech news` | Latest tech headlines | NewsData.io key (prompted via UI) |
| `show my GitHub activity` | Commits, PRs, reviews | GitHub PAT (prompted via UI) |
| `show live cricket scores` | Live match scores | RapidAPI key (prompted via UI) |
| `search elon musk` | Web search results | Serpstack key (prompted via UI) |
| `show my Plane issues` | Plane.so issues board | Plane API key (prompted via UI) |
| `show my upcoming meetings` | Google Calendar events | Google OAuth (prompted via UI) |

### Credential Setup UX

When a widget needs an API key you haven't provided yet, it shows a **setup card** instead of crashing:

1. Explains **why** the widget needs credentials
2. Shows **step-by-step instructions** to get the key
3. Links to the **signup page**
4. Provides **input fields** to paste the key
5. **Validates** the key with a test API call
6. **Saves** and activates the widget

### Widget Lifecycle

Every widget has a lifecycle state visible via badges:

| State | Badge | Meaning |
|---|---|---|
| UNCONFIGURED | — | Missing API key → setup card shown |
| CONFIGURED | — | Key present, not yet fetched |
| ACTIVE | 🟢 ● | Working, auto-refresh running |
| DEGRADED | ⚠️ | API error → refresh paused |
| DISABLED | ⏸️ | User paused the widget |

### Widget Menu (⋯)

Each widget has a 3-dot menu with:
- **Size**: Small / Medium / Large
- **State**: Disable / Enable
- **Settings**: 🔑 Reconfigure (reset API keys)

---

## Project Structure

```
Widget_Forge/
├── backend/
│   ├── main.py                       # FastAPI app, startup, OAuth routes
│   ├── config.py                     # Settings from .env
│   ├── routers/
│   │   └── widgets.py                # API: forge, refresh, credentials, toggle, reconfigure
│   ├── services/
│   │   ├── widget_manifest.py        # Manifest registry, validation, discovery, lifecycle
│   │   ├── credential_store.py       # Scoped credential storage + state persistence
│   │   ├── card_templates.py         # 30+ Adaptive Card generators
│   │   ├── data_engine.py            # Routes intent → connector
│   │   ├── llm_service.py            # Intent parser (rules + LLM fallback)
│   │   └── entity_normalizer.py      # Entity extraction (TSLA, India, etc.)
│   ├── connectors/                   # Data connectors
│   │   ├── github.py                 # GitHub API (commits, PRs, activity)
│   │   ├── news.py                   # NewsData.io
│   │   ├── weather.py                # WeatherAPI + wttr.in fallback
│   │   ├── stock.py                  # Yahoo Finance
│   │   ├── plane.py                  # Plane.so API
│   │   ├── ado.py                    # Azure DevOps API
│   │   ├── cricket.py                # RapidAPI Cricbuzz
│   │   ├── search.py                 # Serpstack Google Search
│   │   ├── google.py                 # Google Calendar/Gmail/YouTube OAuth
│   │   ├── system.py                 # Local system stats (psutil)
│   │   ├── custom.py                 # Counter, timer, clock, checklist
│   │   └── clipboard.py             # Clipboard history
│   ├── store/                        # Persisted data (gitignored)
│   ├── widget_plugins/               # Drop-in plugin directory
│   └── tests/
│       └── test_widget_platform.py   # 43 acceptance tests
├── frontend/
│   ├── index.html                    # Widget Board UI
│   ├── app.js                        # Board logic, auto-refresh, credential setup
│   └── styles.css                    # Responsive grid, state badges
├── WidgetProvider/                   # C# Windows Widget Provider (bridges to real Widget Board)
├── PITCH.md                          # Hackathon pitch document
├── SKILL.md                          # Agent skill definition
├── ARCHITECTURE.md                   # Technical architecture deep-dive
├── .env.example                      # Environment template
└── .gitignore
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/widgets/forge` | Create widget from natural language prompt |
| `POST` | `/api/widgets/refresh` | Refresh a widget's data |
| `POST` | `/api/widgets/credentials` | Save API keys for a widget type |
| `POST` | `/api/widgets/toggle` | Enable/disable a widget |
| `POST` | `/api/widgets/reconfigure` | Reset credentials, show setup card |
| `POST` | `/api/widgets/action` | Interactive actions (counter++, checklist toggle) |
| `GET` | `/api/widgets/list` | List all widgets |
| `GET` | `/api/widgets/manifests` | List all registered widget types with state |
| `GET` | `/api/widgets/manifests/validate` | Validate all manifests |
| `GET` | `/api/widgets/suggestions` | App-aware widget suggestions |
| `GET` | `/api/widgets/credentials` | List saved credentials (masked) |
| `GET` | `/api/widgets/card/{id}` | Raw Adaptive Card JSON |
| `DELETE` | `/api/widgets/{id}` | Delete a widget |
| `GET` | `/health` | Server health check |

---

## Adding a New Widget (Plugin System)

Add new widget types **without writing any code** — just drop a `manifest.json`:

### 1. Create the folder

```
backend/widget_plugins/my_widget/manifest.json
```

### 2. Write the manifest

**No credentials needed:**
```json
{
    "id": "my_widget",
    "name": "My Widget",
    "version": "1.0.0",
    "description": "Does something cool",
    "category": "Utility",
    "keywords": ["my widget", "cool thing"],
    "runtime": {
        "refresh_policy": "none",
        "min_refresh_interval": 0,
        "concurrent_requests": false
    },
    "failure": {
        "on_missing_credentials": "fallback",
        "on_rate_limit": "ignore",
        "on_timeout": "ignore"
    },
    "ui": { "default_size": "md", "icon": "🚀" },
    "capabilities": []
}
```

**With API key:**
```json
{
    "id": "my_api_widget",
    "name": "My API Widget",
    "version": "1.0.0",
    "description": "Needs an API key",
    "category": "Dev",
    "keywords": ["my api"],
    "runtime": {
        "refresh_policy": "interval",
        "min_refresh_interval": 5,
        "concurrent_requests": false
    },
    "failure": {
        "on_missing_credentials": "block",
        "on_rate_limit": "degrade",
        "on_timeout": "retry"
    },
    "ui": { "default_size": "md", "icon": "🔐" },
    "capabilities": [{
        "service_name": "My API",
        "type": "api_key",
        "required": true,
        "scope": "read",
        "config_key": "MY_API_KEY",
        "setup_url": "https://example.com/get-key",
        "setup_steps": [
            "Sign up at example.com",
            "Find API key in settings",
            "Paste it below"
        ],
        "placeholder": "sk-xxxx..."
    }]
}
```

### 3. Restart the server

```bash
uvicorn backend.main:app --reload --port 8000
```

Terminal output:
```
[Plugins] Loaded 1 plugin widget(s): ['my_widget']
[Manifest] All 13 manifests valid ✓
```

### 4. Forge it

Type `"my widget"` or any keyword from the manifest in the prompt bar.

### Manifest Validation Rules

| Field | Rule |
|---|---|
| `id` | Must be `snake_case` |
| `version` | Must be semver (`1.0.0`) |
| `category` | Essentials, Media, Utility, Sports, Google, Dev, Finance, Fun, Work, Gaming, Creative, Web |
| `capabilities[].type` | `api_key`, `oauth`, `pat`, or `none` |
| `capabilities[].scope` | Required for `api_key` / `oauth` / `pat` |
| `capabilities[].setup_steps` | Required when `required: true` |
| `runtime.refresh_policy` | `interval`, `manual`, or `none` |
| `failure.on_missing_credentials` | `block` or `fallback` |

Invalid manifests are **rejected with human-readable errors** at startup.

---

## Running Tests

```bash
python -m pytest backend/tests/test_widget_platform.py -v
```

```
43 passed in 5.12s

TestManifestValidation          11 tests ✅
TestLifecycleStateMachine        5 tests ✅
TestCredentialAccess             6 tests ✅
TestAutoRefreshRules             4 tests ✅
TestFailureHandling              4 tests ✅
TestDynamicDiscovery             4 tests ✅
TestAPIEndpoints                 9 tests ✅
```

---

## How It Maps to the Windows Widget Board

| Widget Forge | Windows Widget Platform |
|---|---|
| Frontend board (HTML + JS) | WidgetBoard.exe (XAML + WebView2) |
| FastAPI backend | WidgetService.exe (singleton COM server) |
| Connectors (Python) | Widget Providers (C++/C# with IWidgetProvider) |
| `manifest.json` plugins | AppxManifest AppExtension declarations |
| `WIDGET_MANIFESTS` dict | WidgetCatalog API |
| Adaptive Card JSON output | **Same format** — directly compatible |
| Plugin discovery at startup | AppExtension change monitoring |
| Prompt bar | Widget Picker (browse-only today) |

The Adaptive Card JSON output is identical to what the real Widget Board consumes.

---

## Security

| Boundary | Enforcement |
|---|---|
| Credentials scoped per widget | `get_credential_for()` validates manifest ownership |
| No cross-widget access | Widget A cannot read Widget B's API key |
| Stored outside widget dir | `backend/store/credentials.json` (gitignored) |
| API keys masked in UI | Displayed as `abc1...xyz9` |
| Platform gates execution | Widget code never touches credentials directly |
| Manifests declarative only | No executable code in manifests |

---

## Environment Variables

All optional. Widget-specific keys can be entered via the UI instead.

| Variable | Purpose | Required |
|---|---|---|
| `GROQ_API_KEY` | Groq LLM (fastest intent parsing) | One LLM needed |
| `GEMINI_API_KEY` | Google Gemini LLM (fallback) | Or this |
| `OLLAMA_ENDPOINT` | Local Ollama (offline) | Or this |
| `GITHUB_TOKEN` | GitHub commits, PRs, activity | Via UI |
| `NEWSDATA_KEY` | News headlines | Via UI |
| `WEATHERAPI_KEY` | Weather (has wttr.in fallback) | Via UI |
| `RAPIDAPI_KEY` | Cricket live scores | Via UI |
| `SERPSTACK_KEY` | Google search results | Via UI |
| `ADO_PAT` | Azure DevOps work items | Via UI |
| `GOOGLE_CLIENT_ID` | Google Calendar/Gmail OAuth | Via UI |

---

## Documentation

| Document | Description |
|---|---|
| [PITCH.md](PITCH.md) | Hackathon pitch — problem, solution, 12 pain points, demo script, roadmap |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical deep-dive — request flows, diagrams, test coverage |
| [SKILL.md](SKILL.md) | Agent skill definition — API schema, lifecycle, plugin examples |

---

## Tech Stack

- **Backend:** Python, FastAPI, uvicorn, httpx, pydantic, psutil
- **Frontend:** Vanilla JS, Adaptive Cards v3.0.4, CSS Grid
- **LLM:** Groq / Gemini / Ollama (rule-based parser handles 90%+ without LLM)
- **Storage:** File-based JSON (credentials, state, widgets)
- **Tests:** pytest (43 acceptance tests)