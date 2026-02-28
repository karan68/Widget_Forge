from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from backend.routers.widgets import router as widgets_router

app = FastAPI(title="Widget Forge", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(widgets_router)

@app.get("/health")
async def health():
    from backend.config import settings
    provider = "groq" if settings.GROQ_API_KEY else "gemini" if settings.GEMINI_API_KEY else "ollama"
    return {"status": "ok", "service": "widget-forge", "llm_provider": provider}

# ─── Google OAuth ──────────────────────────────────────────────

@app.get("/auth/google")
async def google_auth():
    """Redirect user to Google login."""
    from backend.connectors.google import get_auth_url
    return RedirectResponse(get_auth_url())


@app.get("/callback/google")
async def google_callback(code: str = None, error: str = None):
    """Handle Google OAuth callback."""
    if error:
        return HTMLResponse(f"""
            <html><body style="background:#1a1a2e;color:#e0e0e0;font-family:Segoe UI;display:flex;align-items:center;justify-content:center;min-height:100vh">
            <div style="text-align:center"><h2 style="color:#ff6b6b">Google Auth Failed</h2><p>{error}</p>
            <a href="/" style="color:#4285f4">← Back to Widget Forge</a></div></body></html>
        """)

    if not code:
        return HTMLResponse("""
            <html><body style="background:#1a1a2e;color:#e0e0e0;font-family:Segoe UI;display:flex;align-items:center;justify-content:center;min-height:100vh">
            <div style="text-align:center"><h2 style="color:#ff6b6b">No code received</h2>
            <a href="/" style="color:#4285f4">← Back to Widget Forge</a></div></body></html>
        """)

    from backend.connectors.google import exchange_code
    result = await exchange_code(code)

    if result.get("error"):
        return HTMLResponse(f"""
            <html><body style="background:#1a1a2e;color:#e0e0e0;font-family:Segoe UI;display:flex;align-items:center;justify-content:center;min-height:100vh">
            <div style="text-align:center"><h2 style="color:#ff6b6b">Token Error</h2><p>{result['error']}</p>
            <a href="/" style="color:#4285f4">← Back to Widget Forge</a></div></body></html>
        """)

    return HTMLResponse("""
        <html><body style="background:#1a1a2e;color:#e0e0e0;font-family:Segoe UI;display:flex;align-items:center;justify-content:center;min-height:100vh">
        <div style="text-align:center">
            <div style="font-size:48px;margin-bottom:16px">📅</div>
            <h2 style="color:#4285f4">Google Connected!</h2>
            <p style="color:#888">Calendar & Gmail widgets are now available.</p>
            <p style="margin-top:16px"><a href="/" style="color:#4285f4;text-decoration:none;padding:10px 24px;border:1px solid #4285f4;border-radius:8px">← Back to Widget Forge</a></p>
        </div></body></html>
    """)

@app.on_event("startup")
async def startup():
    from backend.config import settings
    
    # Load user-provided credentials from store into settings
    from backend.services.credential_store import load_credentials_into_settings
    load_credentials_into_settings()
    print("[Credentials] Loaded stored credentials into settings")

    # Discover plugin widgets from backend/widget_plugins/
    from backend.services.widget_manifest import (
        discover_plugins, get_discovery_errors, validate_manifest, list_all_manifests,
    )
    plugins = discover_plugins()
    if plugins:
        print(f"[Plugins] Loaded {len(plugins)} plugin widget(s): {[p['id'] for p in plugins]}")
    errors = get_discovery_errors()
    if errors:
        for err in errors:
            print(f"[Plugins] WARNING: {err['path']} → {err['errors']}")

    # Validate all built-in manifests at startup
    invalid_count = 0
    for m in list_all_manifests():
        errs = validate_manifest(m)
        if errs:
            invalid_count += 1
            print(f"[Manifest] WARNING: {m.get('id', '?')} has validation errors: {errs}")
    if invalid_count == 0:
        print(f"[Manifest] All {len(list_all_manifests())} manifests valid ✓")
    
    # Show which LLM provider is active
    if settings.GROQ_API_KEY:
        print(f"[LLM] Groq API configured (model: {settings.GROQ_MODEL})")
    if settings.GEMINI_API_KEY:
        print(f"[LLM] Gemini API configured (model: {settings.GEMINI_MODEL})")
    
    # Test Groq connection
    if settings.GROQ_API_KEY:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
                )
                if response.status_code == 200:
                    print("[LLM] Groq API connected successfully")
                else:
                    print(f"[LLM] Groq API returned {response.status_code}")
        except Exception as e:
            print(f"[LLM] Groq pre-warm failed: {e}")
    
    print(f"[PWA] Widget Forge ready at http://localhost:8000")
    print(f"[PWA] Install as PWA from Edge to get widgets on Widget Board")

# ─── PWA-required routes ───────────────────────────────────────

# Service worker must be served from root scope
@app.get("/sw.js")
async def service_worker():
    return FileResponse("frontend/sw.js", media_type="application/javascript",
                       headers={"Service-Worker-Allowed": "/"})

# Manifest must be accessible
@app.get("/manifest.json")
async def manifest():
    return FileResponse("frontend/manifest.json", media_type="application/manifest+json")

# Serve frontend — must be last (catch-all mount)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
