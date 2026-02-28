import httpx
import base64
from backend.config import settings

def _get_auth_header() -> dict:
    token = base64.b64encode(f":{settings.ADO_PAT}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

BASE_URL = f"https://dev.azure.com/{settings.ADO_ORG}/{settings.ADO_PROJECT}/_apis"

async def get_bugs_by_priority() -> dict:
    """Fetch open bugs grouped by priority."""
    wiql = {
        "query": (
            "SELECT [System.Id], [System.Title], "
            "[Microsoft.VSTS.Common.Priority], [System.State] "
            "FROM WorkItems "
            "WHERE [System.WorkItemType] = 'Bug' "
            "AND [System.State] NOT IN ('Closed', 'Resolved', 'Done') "
            "ORDER BY [Microsoft.VSTS.Common.Priority] ASC"
        )
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Run WIQL to get work item IDs
        resp = await client.post(
            f"{BASE_URL}/wit/wiql?api-version=7.1",
            json=wiql,
            headers=_get_auth_header(),
        )
        resp.raise_for_status()
        ids = [item["id"] for item in resp.json().get("workItems", [])]

        if not ids:
            return {"total": 0, "by_priority": {}, "bugs": []}

        # Step 2: Fetch work item details (batch of up to 200)
        ids_str = ",".join(str(i) for i in ids[:200])
        fields = "System.Id,System.Title,Microsoft.VSTS.Common.Priority,System.State,System.AssignedTo"
        resp2 = await client.get(
            f"{BASE_URL}/wit/workitems?ids={ids_str}&fields={fields}&api-version=7.1",
            headers=_get_auth_header(),
        )
        resp2.raise_for_status()

        bugs = []
        by_priority = {}
        for wi in resp2.json().get("value", []):
            f = wi["fields"]
            priority = f.get("Microsoft.VSTS.Common.Priority", 4)
            bug = {
                "id": wi["id"],
                "title": f.get("System.Title", ""),
                "priority": priority,
                "state": f.get("System.State", ""),
                "assigned_to": f.get("System.AssignedTo", {}).get("displayName", "Unassigned"),
            }
            bugs.append(bug)
            key = f"P{priority}"
            by_priority[key] = by_priority.get(key, 0) + 1

        return {
            "total": len(bugs),
            "by_priority": by_priority,
            "bugs": bugs[:20],  # Top 20 for display
        }
