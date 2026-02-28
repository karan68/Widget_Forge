"""
News connector using NewsData.io API.
Supports: latest news, crypto news, market news, topic search, country/language filters.
"""
import httpx
from backend.config import settings

NEWSDATA_BASE = "https://newsdata.io/api/1"


async def get_news(
    query: str = None,
    category: str = None,
    country: str = None,
    language: str = "en",
    count: int = 8,
    endpoint: str = "latest",
) -> dict:
    """
    Fetch news from NewsData.io.

    Args:
        query:    Search keywords (e.g. "microsoft", "cricket")
        category: business, crime, domestic, education, entertainment,
                  environment, food, health, lifestyle, other, politics,
                  science, sports, technology, top, tourism, world
        country:  ISO 3166-1 alpha-2 (e.g. "in", "us", "gb")
        language: ISO 639-1 (default "en")
        count:    Max articles (1-10 for free tier)
        endpoint: "latest" | "crypto" | "market"
    """
    api_key = settings.NEWSDATA_KEY
    if not api_key:
        return {"error": "NewsData.io API key not configured", "articles": []}

    ep = endpoint if endpoint in ("latest", "crypto", "market") else "latest"
    url = f"{NEWSDATA_BASE}/{ep}"

    params = {
        "apikey": api_key,
        "language": language,
        "size": min(count, 10),
        "removeduplicate": 1,
        "image": 1,
    }
    if query:
        params["q"] = query
    if category:
        params["category"] = category
    if country:
        params["country"] = country

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        if data.get("status") != "success":
            return {
                "error": data.get("results", {}).get("message", "API error"),
                "articles": [],
            }

        articles = []
        for item in data.get("results", []):
            articles.append({
                "id": item.get("article_id", ""),
                "title": item.get("title", "No title"),
                "description": (item.get("description") or "")[:200],
                "url": item.get("link", ""),
                "image": item.get("image_url"),
                "source": item.get("source_name", ""),
                "source_icon": item.get("source_icon"),
                "author": (item.get("creator") or [None])[0] if isinstance(item.get("creator"), list) else item.get("creator"),
                "published": (item.get("pubDate") or "")[:16],
                "category": (item.get("category") or [None])[0] if isinstance(item.get("category"), list) else item.get("category"),
                "country": (item.get("country") or [None])[0] if isinstance(item.get("country"), list) else item.get("country"),
                "sentiment": item.get("sentiment"),
                "keywords": item.get("keywords", []),
            })

        return {
            "articles": articles,
            "count": len(articles),
            "total": data.get("totalResults", 0),
            "query": query,
            "category": category,
            "endpoint": ep,
            "type": "news",
        }

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "articles": []}
    except Exception as e:
        return {"error": str(e), "articles": []}


async def get_crypto_news(query: str = None, count: int = 8) -> dict:
    """Crypto/blockchain news endpoint."""
    return await get_news(query=query, count=count, endpoint="crypto")


async def get_market_news(query: str = None, count: int = 8) -> dict:
    """Finance/stock/market news endpoint."""
    return await get_news(query=query, count=count, endpoint="market")


# Keep backward compatibility alias
async def get_top_stories(count: int = 10, topic: str = None) -> dict:
    """Backward-compatible wrapper."""
    result = await get_news(query=topic, count=count)
    result["stories"] = result.get("articles", [])
    result["topic"] = topic
    return result