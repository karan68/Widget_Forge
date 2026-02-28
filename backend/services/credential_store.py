"""
Credential Store
────────────────
File-based credential storage, scoped per widget type.
Credentials are entered via UI and loaded dynamically at runtime.

Storage: backend/store/credentials.json
Format:  { "config_key": "value", ... }

Widget State Storage: backend/store/widget_states.json
Format:  { "widget_id": "active", ... }

Security:
  - Credentials stored outside widget directories
  - Widgets cannot access credentials directly — platform gates access
  - Keys are masked in UI/logs
  - Scoped access: get_credential_for() validates key ownership
"""

import json
import os
from pathlib import Path
from backend.services.widget_manifest import (
    get_manifest, get_required_capabilities, get_all_capabilities,
    get_credential_keys_for, WidgetState,
)

CRED_STORE_PATH = Path("backend/store/credentials.json")
STATE_STORE_PATH = Path("backend/store/widget_states.json")


# ─── Widget State Persistence ─────────────────────────────────

def _load_state_store() -> dict:
    """Load persisted widget states from disk."""
    if STATE_STORE_PATH.exists():
        try:
            return json.loads(STATE_STORE_PATH.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_state_store(store: dict):
    """Save widget states to disk."""
    STATE_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_STORE_PATH.write_text(json.dumps(store, indent=2))


def set_widget_lifecycle_state(widget_id: str, state: str):
    """Persist the lifecycle state for a specific widget instance."""
    store = _load_state_store()
    store[widget_id] = state
    _save_state_store(store)


def get_widget_lifecycle_state(widget_id: str) -> str | None:
    """Get the persisted lifecycle state for a widget instance."""
    store = _load_state_store()
    return store.get(widget_id)


# ─── Store Operations ─────────────────────────────────────────

def _load_store() -> dict:
    """Load the credential store from disk."""
    if CRED_STORE_PATH.exists():
        try:
            return json.loads(CRED_STORE_PATH.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_store(store: dict):
    """Save the credential store to disk."""
    CRED_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRED_STORE_PATH.write_text(json.dumps(store, indent=2))


def get_credential(config_key: str) -> str | None:
    """
    Get a credential value. Checks:
    1. Credential store (user-provided via UI)
    2. Settings object (loaded from .env at startup)
    3. Environment variable (direct fallback)
    """
    store = _load_store()
    val = store.get(config_key)
    if val:
        return val
    # Fallback to settings object (which loads from .env)
    try:
        from backend.config import settings
        env_val = getattr(settings, config_key, "")
        if env_val:
            return env_val
    except Exception:
        pass
    # Last fallback: direct env
    return os.getenv(config_key, "") or None


def get_credential_for(data_source: str, config_key: str) -> str | None:
    """
    Scoped credential access — only returns the credential if config_key
    belongs to the given widget type's manifest. Prevents cross-widget
    credential leakage.
    """
    allowed_keys = get_credential_keys_for(data_source)
    if allowed_keys and config_key not in allowed_keys:
        return None  # key not owned by this widget type
    return get_credential(config_key)


def set_credential(config_key: str, value: str):
    """Set a credential in the store."""
    store = _load_store()
    store[config_key] = value.strip()
    _save_store(store)


def set_credentials(credentials: dict[str, str]):
    """Set multiple credentials at once."""
    store = _load_store()
    for key, value in credentials.items():
        if value and value.strip():
            store[key] = value.strip()
    _save_store(store)


def delete_credential(config_key: str):
    """Remove a credential from the store."""
    store = _load_store()
    store.pop(config_key, None)
    _save_store(store)


def list_credentials() -> dict[str, str]:
    """List all stored credentials (values masked)."""
    store = _load_store()
    masked = {}
    for key, val in store.items():
        if val and len(val) > 8:
            masked[key] = val[:4] + "..." + val[-4:]
        elif val:
            masked[key] = "****"
        else:
            masked[key] = ""
    return masked


# ─── Lifecycle State Check ────────────────────────────────────

def check_widget_state(data_source: str) -> dict:
    """
    Check the lifecycle state of a widget type.

    Returns:
        {
            "state": WidgetState,
            "missing": [list of missing required capabilities],
            "configured": [list of configured capabilities],
            "manifest": the widget manifest,
        }
    """
    manifest = get_manifest(data_source)
    if not manifest:
        # Unknown widget type — no manifest, treat as no requirements
        return {
            "state": WidgetState.CONFIGURED,
            "missing": [],
            "configured": [],
            "manifest": None,
        }

    capabilities = manifest.get("capabilities", [])
    if not capabilities:
        # No credentials needed
        return {
            "state": WidgetState.CONFIGURED,
            "missing": [],
            "configured": [],
            "manifest": manifest,
        }

    missing = []
    configured = []

    for cap in capabilities:
        # Check if credentials exist
        if cap.get("fields"):
            # Multi-field capability (e.g., Google OAuth)
            all_present = True
            for field in cap["fields"]:
                val = get_credential(field["key"])
                if not val and not field.get("default"):
                    all_present = False
            if all_present:
                configured.append(cap)
            elif cap.get("required"):
                missing.append(cap)
        elif cap.get("config_keys"):
            # Multiple keys for one capability
            all_present = all(get_credential(k) for k in cap["config_keys"])
            if all_present:
                configured.append(cap)
            elif cap.get("required"):
                missing.append(cap)
        else:
            # Single key capability
            val = get_credential(cap.get("config_key", ""))
            if val:
                configured.append(cap)
            elif cap.get("required"):
                missing.append(cap)

    state = WidgetState.UNCONFIGURED if missing else WidgetState.CONFIGURED

    return {
        "state": state,
        "missing": missing,
        "configured": configured,
        "manifest": manifest,
    }


def is_widget_configured(data_source: str) -> bool:
    """Quick check: are all required credentials present?"""
    result = check_widget_state(data_source)
    return result["state"] != WidgetState.UNCONFIGURED


# ─── Dynamic Config Loading ──────────────────────────────────
# This patches the settings object at runtime so connectors
# can use `settings.WHATEVER_KEY` without changes.

def load_credentials_into_settings():
    """
    Load all stored credentials into the settings object.
    This allows connectors to use settings.X without modification.
    Called at startup and after credential updates.
    """
    from backend.config import settings
    store = _load_store()
    for key, value in store.items():
        if value and hasattr(settings, key):
            setattr(settings, key, value)
        elif value:
            # Also set it — the settings object accepts dynamic attrs
            setattr(settings, key, value)


def reload_credentials_for(data_source: str):
    """Reload credentials for a specific widget type into settings."""
    from backend.config import settings
    manifest = get_manifest(data_source)
    if not manifest:
        return
    for cap in manifest.get("capabilities", []):
        if cap.get("fields"):
            for field in cap["fields"]:
                val = get_credential(field["key"])
                if val:
                    setattr(settings, field["key"], val)
                elif field.get("default"):
                    setattr(settings, field["key"], field["default"])
        elif cap.get("config_keys"):
            for k in cap["config_keys"]:
                val = get_credential(k)
                if val:
                    setattr(settings, k, val)
        else:
            key = cap.get("config_key", "")
            val = get_credential(key)
            if val:
                setattr(settings, key, val)
