# Widget Forge — Agent Skill Definition

## Skill Name
`forge_widget`

## Description
Takes a natural language description of a desired widget and produces a live, auto-refreshing Adaptive Card widget with real-time data. The agent handles intent parsing, credential gating, data fetching, card generation, and lifecycle management autonomously.

## Input
- `prompt` (string): Natural language description of the desired widget

### Example Prompts
```
"track TSLA stock"
"show tech news from India"
"show my Plane issues"
"5 min timer"
"show system health"
"show my GitHub activity"
"search elon musk"
"show live cricket scores"
"clock widget"
"checklist: standup, review PRs, deploy"
```

## Output
```json
{
    "widget_id": "a1b2c3d4",
    "prompt": "track TSLA stock",
    "intent": {
        "data_source": "stock",
        "data_type": "price",
        "entity": "TSLA"
    },
    "adaptive_card": { },
    "data": { },
    "widget_state": "active",
    "refresh_minutes": 5
}
```

### Output Fields
| Field | Type | Description |
|---|---|---|
| `widget_id` | string | Unique identifier for the created widget |
| `adaptive_card` | object | Adaptive Card v1.6 JSON — renderable by any Adaptive Card host |
| `data` | object | Raw data from connector |
| `widget_state` | enum | `UNCONFIGURED` &#124; `CONFIGURED` &#124; `ACTIVE` &#124; `DEGRADED` &#124; `DISABLED` |
| `refresh_minutes` | number | Auto-refresh interval (0 = no refresh) |

## Capabilities Required
- Declared per widget type in `manifest.json`
- Platform collects credentials via setup card UX when missing
- No hardcoded environment variables

### Capability Types
| Type | Description | Example |
|---|---|---|
| `api_key` | Single API key | NewsData.io, Serpstack, WeatherAPI |
| `oauth` | OAuth 2.0 flow | Google Calendar, Gmail, Spotify |
| `pat` | Personal Access Token | GitHub, Azure DevOps |
| `none` | No credentials needed | System monitor, Clock, Timer |

## Lifecycle

```
1. User provides prompt
2. Agent parses intent (data_source, data_type, entity, parameters)
3. Agent checks credential state from widget manifest
4. If UNCONFIGURED:
   → Returns setup card with instructions + input fields
   → No API calls made (execution blocked)
5. If CONFIGURED:
   → Fetches data from connector
   → Generates Adaptive Card
   → State transitions to ACTIVE
   → Auto-refresh starts
6. If API error / rate limit:
   → State transitions to DEGRADED
   → Auto-refresh paused
   → User notified with ⚠️ badge
7. User can:
   → Reconfigure (🔑) → clears credentials → UNCONFIGURED
   → Disable (⏸️) → pauses widget → DISABLED
   → Enable (▶️) → resumes widget → ACTIVE
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/widgets/forge` | Create a widget from natural language |
| `POST` | `/api/widgets/refresh` | Refresh a widget's data |
| `POST` | `/api/widgets/credentials` | Save credentials for a widget type |
| `POST` | `/api/widgets/toggle` | Enable/disable a widget |
| `POST` | `/api/widgets/reconfigure` | Reset credentials and show setup card |
| `GET` | `/api/widgets/list` | List all created widgets |
| `GET` | `/api/widgets/manifests` | List all registered widget types |
| `GET` | `/api/widgets/manifests/validate` | Validate all manifests |
| `DELETE` | `/api/widgets/{id}` | Delete a widget |

## How an External Agent Would Use This

```python
import requests

BASE = "http://localhost:8000/api/widgets"

# Step 1: Agent decides user needs a stock widget
response = requests.post(f"{BASE}/forge",
    json={"prompt": "track MSFT stock"})
widget = response.json()

# Step 2: Check if credentials are needed
if widget.get("adaptive_card", {}).get("_credential_setup"):
    # Widget needs API credentials
    setup = widget["adaptive_card"]["_credential_setup"]
    print(f"Widget needs: {setup['widget_name']}")
    for field in setup["fields"]:
        print(f"  - {field['label']}: {field['placeholder']}")
    
    # Agent could fetch credentials from a vault and submit them
    requests.post(f"{BASE}/credentials", json={
        "data_source": setup["data_source"],
        "credentials": {"API_KEY": "value_from_vault"}
    })
else:
    # Widget is live — agent can embed the adaptive card in any surface
    card = widget["adaptive_card"]
    state = widget["widget_state"]  # "active"
    print(f"Widget created: {widget['widget_id']} (state: {state})")

# Step 3: Agent can refresh widget later
requests.post(f"{BASE}/refresh",
    json={"widget_id": widget["widget_id"]})

# Step 4: Agent can disable widget when no longer needed
requests.post(f"{BASE}/toggle",
    json={"widget_id": widget["widget_id"], "enabled": False})
```

## Plugin Registration

New widget types can be added by dropping a `manifest.json` file:

```
backend/widget_plugins/<widget_id>/manifest.json
```

### Minimal Manifest (No Credentials)
```json
{
    "id": "quote_of_day",
    "name": "Quote of the Day",
    "version": "1.0.0",
    "description": "Daily inspirational quote",
    "category": "Fun",
    "keywords": ["quote", "inspiration", "motivational"],
    "runtime": { "refresh_policy": "interval", "min_refresh_interval": 60, "concurrent_requests": false },
    "failure": { "on_missing_credentials": "fallback", "on_rate_limit": "ignore", "on_timeout": "ignore" },
    "ui": { "default_size": "sm", "icon": "💬" },
    "capabilities": []
}
```

### Manifest with API Key Requirement
```json
{
    "id": "my_api_widget",
    "name": "My API Widget",
    "version": "1.0.0",
    "description": "Widget that needs an API key",
    "category": "Dev",
    "keywords": ["my api", "custom api"],
    "runtime": { "refresh_policy": "interval", "min_refresh_interval": 5, "concurrent_requests": false },
    "failure": { "on_missing_credentials": "block", "on_rate_limit": "degrade", "on_timeout": "retry" },
    "ui": { "default_size": "md", "icon": "🔐" },
    "capabilities": [{
        "service_name": "My Custom API",
        "type": "api_key",
        "required": true,
        "scope": "read_data",
        "config_key": "MY_CUSTOM_API_KEY",
        "setup_url": "https://example.com/get-key",
        "setup_steps": ["Sign up at example.com", "Find API key in settings", "Paste it below"],
        "placeholder": "sk-xxxxxxxxxxxx"
    }]
}
```

The platform discovers, validates, and registers the plugin at startup. Prompts containing the widget's name, id, or keywords will route to it automatically.
