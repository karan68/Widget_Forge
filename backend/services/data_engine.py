from backend.connectors import ado, github
from backend.connectors import google as google_cal
from backend.connectors import weather, news, system, stock, custom, cricket, clipboard, search, plane
from backend.config import settings

async def fetch_data(intent: dict) -> dict:
    """Route to the right connector based on intent."""
    source = intent["data_source"]
    data_type = intent.get("data_type", "")

    if source == "ado":
        if data_type in ("bugs", "work_items"):
            return await ado.get_bugs_by_priority()
        return await ado.get_bugs_by_priority()

    elif source == "google":
        if data_type in ("meetings", "calendar"):
            count = intent.get("count", 5)
            return await google_cal.get_google_data(data_type="calendar", count=count)
        elif data_type in ("gmail", "gmail_latest", "gmail_summary"):
            count = intent.get("count", 5)
            sender = intent.get("sender")
            return await google_cal.get_google_data(data_type=data_type, count=count, sender=sender)
        elif data_type in ("youtube", "youtube_search"):
            query = intent.get("query", "music")
            count = intent.get("count", 5)
            return await google_cal.get_google_data(data_type="youtube", query=query, count=count)
        return await google_cal.get_google_data()

    elif source == "github":
        if data_type == "commits":
            return await github.get_daily_commits()
        elif data_type == "prs":
            return await github.get_open_prs()
        elif data_type == "activity":
            return await github.get_github_activity()
        elif data_type == "standup":
            return await github.get_standup_data()
        return await github.get_github_activity()

    elif source == "weather":
        cities = intent.get("cities", intent.get("filters", {}).get("cities", []))
        if isinstance(cities, str):
            cities = [cities]
        # If LLM split "gachibowli, hyderabad, india" into separate items, 
        # join them back into one location query
        if cities and len(cities) > 1:
            # Check if these look like parts of one address (common pattern from LLM)
            # If any item looks like a country/state, join them all as one location
            location_parts = ["india", "usa", "uk", "china", "japan", "australia", "canada", 
                            "telangana", "maharashtra", "karnataka", "delhi", "mumbai",
                            "california", "texas", "new york", "florida"]
            is_single_location = any(c.lower().strip() in location_parts for c in cities)
            if is_single_location:
                # Treat as one location
                cities = [" ".join(c.strip() for c in cities)]
        if not cities:
            cities = [""]  # Auto-detect
        return await weather.get_weather(cities)

    elif source == "news":
        query = intent.get("query", intent.get("topic"))
        count = intent.get("count", 8)
        category = intent.get("category")
        country = intent.get("country")
        endpoint = data_type if data_type in ("latest", "crypto", "market") else "latest"
        return await news.get_news(
            query=query, category=category, country=country,
            count=count, endpoint=endpoint,
        )

    elif source == "system":
        if data_type == "battery":
            return system.get_battery_health()
        elif data_type == "disk_space":
            return system.get_disk_space()
        elif data_type == "network":
            return system.get_network_monitor()
        elif data_type == "clipboard":
            return clipboard.get_clipboard_history()

        process_filter = intent.get("process") or intent.get("app") or intent.get("filters", {}).get("process")
        title = intent.get("title", "").lower()
        if not process_filter:
            for app in ["chrome", "code", "vscode", "firefox", "edge", "teams", "slack", "spotify", "discord", "python", "node"]:
                if app in title:
                    process_filter = app
                    break
        if process_filter:
            return system.get_process_metrics(process_filter)
        else:
            return system.get_system_health()

    elif source == "stock":
        symbol = intent.get("symbol", "")
        if not symbol:
            # Try to extract from title
            title = intent.get("title", "")
            # Common stock name → symbol mapping
            name_map = {
                "adobe": "ADBE", "apple": "AAPL", "microsoft": "MSFT",
                "google": "GOOGL", "alphabet": "GOOGL", "amazon": "AMZN",
                "tesla": "TSLA", "meta": "META", "facebook": "META",
                "netflix": "NFLX", "nvidia": "NVDA", "amd": "AMD",
                "intel": "INTC", "disney": "DIS", "spotify": "SPOT",
            }
            for name, sym in name_map.items():
                if name in title.lower():
                    symbol = sym
                    break
            if not symbol:
                symbol = "AAPL"  # default
        return await stock.get_stock_price(symbol)

    elif source == "custom":
        return custom.get_custom_data(intent)

    elif source == "cricket":
        return await cricket.get_cricket_scores()

    elif source == "search":
        query = intent.get("query", "")
        search_type = data_type if data_type in ("web", "images", "videos", "news") else "web"
        return await search.google_search(query=query, search_type=search_type)

    elif source == "plane":
        return await plane.get_plane_issues(count=intent.get("count", 10))

    elif source == "composite":
        if data_type == "my_day":
            # Gather data from multiple sources
            import asyncio
            results = {}
            try:
                results["calendar"] = await google_cal.get_google_data(data_type="calendar", count=5)
            except Exception:
                results["calendar"] = {}
            try:
                results["gmail"] = await google_cal.get_google_data(data_type="gmail_summary", count=3)
            except Exception:
                results["gmail"] = {}
            try:
                results["weather"] = await weather.get_weather([""])
            except Exception:
                results["weather"] = {}
            results["type"] = "my_day"
            return results

    # Unknown / plugin source — return placeholder data
    # The credential check in forge() will show the setup card if needed
    from backend.services.widget_manifest import get_manifest
    manifest = get_manifest(source)
    if manifest:
        return {
            "type": "plugin",
            "data_source": source,
            "title": manifest.get("name", source),
            "description": manifest.get("description", ""),
            "icon": manifest.get("ui", {}).get("icon", "🧩"),
            "message": f"{manifest.get('name', source)} widget is ready. Data will appear here once a connector is implemented.",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
    return custom.get_custom_data(intent)
