"""
Google Search connector using Serpstack API.
Provides web search, image search, news search, and video search results.
"""
import httpx
from backend.config import settings

SERPSTACK_BASE = "https://api.serpstack.com/search"


async def google_search(
    query: str,
    search_type: str = "web",
    count: int = 8,
    location: str = None,
    period: str = None,
    device: str = "desktop",
    safe: bool = False,
) -> dict:
    """
    Search Google via Serpstack API.

    Args:
        query:       Search query string
        search_type: "web" | "images" | "videos" | "news" | "shopping"
        count:       Number of results to return (max ~10 per page)
        location:    Free-text location for geo-targeting
        period:      "last_hour" | "last_day" | "last_week" | "last_month" | "last_year"
        device:      "desktop" | "mobile" | "tablet"
        safe:        Enable SafeSearch
    """
    api_key = settings.SERPSTACK_KEY
    if not api_key:
        return {"error": "Serpstack API key not configured", "results": []}

    if not query or not query.strip():
        return {"error": "No search query provided", "results": []}

    params = {
        "access_key": api_key,
        "query": query.strip(),
        "type": search_type,
        "device": device,
        "output": "json",
        "safe": 1 if safe else 0,
    }
    if location:
        params["location"] = location
    if period:
        params["period"] = period

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(SERPSTACK_BASE, params=params)
            r.raise_for_status()
            data = r.json()

        if data.get("error"):
            return {
                "error": data["error"].get("info", str(data["error"])),
                "results": [],
            }

        # Parse organic results
        results = []
        for item in data.get("organic_results", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "domain": item.get("displayed_url", item.get("domain", "")),
                "snippet": item.get("snippet", ""),
                "position": item.get("position", 0),
                "cached_url": item.get("cached_page_url"),
            })

        # Parse answer box (featured snippet)
        answer_box = None
        ab = data.get("answer_box")
        if ab:
            answer_box = {
                "title": ab.get("title", ""),
                "answer": ab.get("answer", ab.get("snippet", "")),
                "url": ab.get("url", ""),
            }

        # Parse knowledge graph
        knowledge_graph = None
        kg = data.get("knowledge_graph")
        if kg:
            knowledge_graph = {
                "title": kg.get("title", ""),
                "type": kg.get("type", ""),
                "description": kg.get("description", ""),
                "image": kg.get("image", ""),
                "url": kg.get("website", ""),
                "facts": {},
            }
            # Extract key facts
            for key in ["born", "founded", "headquarters", "ceo", "revenue",
                        "employees", "height", "weight", "spouse", "nationality",
                        "net_worth", "education", "known_for"]:
                if kg.get(key):
                    knowledge_graph["facts"][key.replace("_", " ").title()] = kg[key]

        # Search metadata
        search_info = data.get("search_information", {})

        return {
            "type": "search",
            "query": query,
            "search_type": search_type,
            "results": results,
            "answer_box": answer_box,
            "knowledge_graph": knowledge_graph,
            "total_results": search_info.get("total_results", 0),
            "time_taken": search_info.get("time_taken_displayed", ""),
            "count": len(results),
        }

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "results": []}
    except Exception as e:
        return {"error": str(e), "results": []}
