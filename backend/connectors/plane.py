"""
Plane.so connector — Issues, cycles, and modules.
Uses Plane REST API with personal access token authentication.
"""
import httpx
from backend.config import settings
from backend.services.credential_store import get_credential


def _get_config() -> tuple[str, str, str]:
    """Get Plane API config from credential store."""
    api_key = get_credential("PLANE_API_KEY") or ""
    workspace = get_credential("PLANE_WORKSPACE") or ""
    base_url = get_credential("PLANE_BASE_URL") or "https://api.plane.so"
    # Normalise: strip trailing slashes, ensure we use the API domain
    base_url = base_url.rstrip("/")
    # Common mistake: user pastes the web UI URL instead of the API URL
    if "app.plane.so" in base_url:
        base_url = base_url.replace("app.plane.so", "api.plane.so")
    return api_key, workspace, base_url


def _safe_json(response: httpx.Response) -> dict | list | None:
    """Parse JSON response safely, returning None if body is empty or not JSON."""
    ct = response.headers.get("content-type", "")
    if "application/json" not in ct and "text/json" not in ct:
        return None
    text = response.text.strip()
    if not text:
        return None
    try:
        return response.json()
    except Exception:
        return None


async def get_plane_issues(project_id: str = None, count: int = 10) -> dict:
    """Fetch recent work items from Plane."""
    api_key, workspace, base_url = _get_config()

    if not api_key or not workspace:
        return {
            "error": "not_configured",
            "message": "Plane API key and workspace are required",
            "issues": [],
        }

    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # First get projects if no project_id specified
            if not project_id:
                r = await client.get(
                    f"{base_url}/api/v1/workspaces/{workspace}/projects/",
                    headers=headers,
                )
                if r.status_code == 403:
                    return {"error": "Invalid API key. Please reconfigure your Plane credentials.",
                            "issues": [], "type": "plane"}
                if r.status_code == 401:
                    return {"error": "Invalid API key. Please reconfigure your Plane credentials.",
                            "issues": [], "type": "plane"}
                r.raise_for_status()

                projects = _safe_json(r)
                if projects is None:
                    return {"error": "Plane API returned a non-JSON response. "
                            "Make sure the Base URL points to the API (api.plane.so), "
                            "not the web UI (app.plane.so).",
                            "issues": [], "type": "plane"}

                if isinstance(projects, dict):
                    projects = projects.get("results", [])
                if not projects:
                    return {"error": "No projects found in this workspace", "issues": [], "type": "plane"}

                # Pick the first project that actually has issues
                # (avoids returning 0 results from an empty starter project)
                project_id = projects[0].get("id", "")
                if len(projects) > 1:
                    for proj in projects:
                        pid = proj.get("id", "")
                        probe_url = f"{base_url}/api/v1/workspaces/{workspace}/projects/{pid}/issues/"
                        probe = await client.get(probe_url, headers=headers, params={"per_page": 1})
                        probe_data = _safe_json(probe)
                        total = 0
                        if isinstance(probe_data, dict):
                            total = probe_data.get("total_count", probe_data.get("count", 0))
                        if total > 0:
                            project_id = pid
                            break

            # Try fetching issues — Plane API uses both /issues/ and /work-items/
            issue_url = None
            for endpoint in ["issues", "work-items"]:
                url = f"{base_url}/api/v1/workspaces/{workspace}/projects/{project_id}/{endpoint}/"
                r = await client.get(url, headers=headers,
                                     params={"per_page": count, "expand": "state,assignees"})
                if r.status_code == 200:
                    issue_url = url
                    break
                if r.status_code in (401, 403):
                    return {"error": "Invalid API key. Please reconfigure your Plane credentials.",
                            "issues": [], "type": "plane"}

            if issue_url is None:
                r.raise_for_status()  # will throw with last status

            data = _safe_json(r)
            if data is None:
                return {"error": "Plane API returned empty or non-JSON response.",
                        "issues": [], "type": "plane"}

            items = data.get("results", []) if isinstance(data, dict) else data
            if isinstance(items, dict):
                items = list(items.values()) if items else []

            issues = []
            for item in items[:count]:
                if not isinstance(item, dict):
                    continue
                state = item.get("state_detail") or item.get("state", {})
                if isinstance(state, str):
                    state = {"name": state}

                assignees = item.get("assignee_detail") or item.get("assignees", [])
                assignee_names = []
                if isinstance(assignees, list):
                    for a in assignees:
                        if isinstance(a, dict):
                            assignee_names.append(a.get("display_name", a.get("email", "")))

                issues.append({
                    "id": item.get("id", ""),
                    "sequence_id": item.get("sequence_id", ""),
                    "name": item.get("name", "Untitled"),
                    "description": (item.get("description_stripped") or "")[:200],
                    "state": state.get("name", "Unknown") if isinstance(state, dict) else str(state),
                    "priority": item.get("priority", "none"),
                    "assignees": assignee_names,
                    "created_at": (item.get("created_at") or "")[:10],
                    "updated_at": (item.get("updated_at") or "")[:10],
                    "labels": [l.get("name", "") for l in (item.get("label_detail") or []) if isinstance(l, dict)],
                })

            return {
                "issues": issues,
                "count": len(issues),
                "project_id": project_id,
                "workspace": workspace,
                "type": "plane",
            }

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body = _safe_json(e.response)
        detail = body.get("detail", "") if isinstance(body, dict) else ""
        if status in (401, 403):
            return {"error": f"Invalid API key ({status}). {detail}".strip(),
                    "issues": [], "type": "plane"}
        if status == 404:
            return {"error": f"Workspace or project not found. {detail}".strip(),
                    "issues": [], "type": "plane"}
        return {"error": f"Plane API error {status}. {detail}".strip(),
                "issues": [], "type": "plane"}
    except Exception as e:
        return {"error": str(e), "issues": [], "type": "plane"}
