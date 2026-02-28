from datetime import datetime, timezone

def bugs_by_priority_card(data: dict) -> dict:
    """Fallback template for ADO bugs by priority."""
    body = [
        {"type": "TextBlock", "text": "🐛 Open Bugs by Priority", "size": "Large", "weight": "Bolder"},
        {"type": "TextBlock", "text": f"Total: {data['total']} bugs", "spacing": "Small"},
    ]
    # Priority bars
    columns = []
    colors = {"P1": "Attention", "P2": "Warning", "P3": "Accent", "P4": "Good"}
    for pri, count in sorted(data.get("by_priority", {}).items()):
        columns.append({
            "type": "Column",
            "width": "auto",
            "items": [
                {"type": "TextBlock", "text": str(count), "size": "ExtraLarge", "weight": "Bolder",
                 "horizontalAlignment": "Center", "color": colors.get(pri, "Default")},
                {"type": "TextBlock", "text": pri, "horizontalAlignment": "Center",
                 "size": "Small", "isSubtle": True},
            ],
        })
    if columns:
        body.append({"type": "ColumnSet", "columns": columns, "spacing": "Medium"})

    # Top bugs list
    body.append({"type": "TextBlock", "text": "Top bugs:", "weight": "Bolder", "spacing": "Medium", "separator": True})
    for bug in data.get("bugs", [])[:5]:
        body.append({"type": "TextBlock", "text": f"• P{bug['priority']} — {bug['title'][:50]}", "size": "Small", "wrap": True})

    # Footer
    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


def meetings_card(data: dict) -> dict:
    """Fallback template for next meetings (Graph/Outlook)."""
    body = [
        {"type": "TextBlock", "text": "📅 Upcoming Meetings", "size": "Large", "weight": "Bolder"},
    ]
    for m in data.get("meetings", []):
        items = [
            {"type": "TextBlock", "text": m.get("title", m.get("subject", "Meeting")), "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": f"🕐 {m['start']} — {m.get('attendee_count', m.get('attendees', 0))} attendees",
             "size": "Small", "isSubtle": True},
        ]
        container = {"type": "Container", "items": items, "spacing": "Small", "separator": True}
        if m.get("join_url"):
            container["selectAction"] = {"type": "Action.OpenUrl", "url": m["join_url"], "title": "Join"}
        body.append(container)

    if not data.get("meetings"):
        body.append({"type": "TextBlock", "text": "No upcoming meetings 🎉", "isSubtle": True})

    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


def google_meetings_card(data: dict) -> dict:
    """Fallback template for Google Calendar meetings."""
    body = [
        {"type": "TextBlock", "text": "📆 Google Calendar", "size": "Large", "weight": "Bolder"},
    ]
    for m in data.get("meetings", []):
        items = [
            {"type": "TextBlock", "text": m.get("subject", "Event"), "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": f"🕐 {m['start']}", "size": "Small", "isSubtle": True},
        ]
        if m.get("location"):
            items.append({"type": "TextBlock", "text": f"📍 {m['location']}", "size": "Small", "isSubtle": True})
        
        container = {"type": "Container", "items": items, "spacing": "Small", "separator": True}
        if m.get("join_url"):
            container["selectAction"] = {"type": "Action.OpenUrl", "url": m["join_url"], "title": "Join Meet"}
        body.append(container)

    if not data.get("meetings"):
        body.append({"type": "TextBlock", "text": "No upcoming events 🎉", "isSubtle": True})

    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


def youtube_card(data: dict) -> dict:
    """Template for YouTube search results — rendered as custom widget in frontend."""
    # Auth required
    if data.get("error") in ("not_authenticated", "scope_missing"):
        body = [
            {"type": "TextBlock", "text": "▶️ YouTube", "size": "Medium", "weight": "Bolder"},
            {"type": "TextBlock", "text": data.get("message", "Connect Google account"), "wrap": True, "isSubtle": True},
            {"type": "ActionSet", "actions": [
                {"type": "Action.OpenUrl", "title": "Connect Google", "url": data.get("auth_url", "/auth/google")}
            ]},
        ]
        return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}

    if data.get("error"):
        body = [
            {"type": "TextBlock", "text": "▶️ YouTube", "size": "Medium", "weight": "Bolder"},
            {"type": "TextBlock", "text": str(data["error"]), "color": "Attention", "wrap": True},
        ]
        return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}

    # Return a special card that the frontend renders as a YouTube player
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": [{"type": "TextBlock", "text": "Loading YouTube..."}],
        # Custom data for the frontend YouTube renderer
        "_youtube": {
            "videos": data.get("videos", []),
            "query": data.get("query", ""),
        },
    }


def gmail_card(data: dict) -> dict:
    """Template for Gmail emails widget."""
    import html as html_mod
    body = []

    # Auth required
    if data.get("error") in ("auth_expired", "not_authenticated"):
        body.append({"type": "TextBlock", "text": "📧 Gmail", "size": "Medium", "weight": "Bolder"})
        body.append({"type": "TextBlock", "text": data.get("message", "Connect your Google account"), "wrap": True, "isSubtle": True})
        body.append({"type": "ActionSet", "actions": [
            {"type": "Action.OpenUrl", "title": "Connect Google", "url": data.get("auth_url", "/auth/google")}
        ]})
        return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}

    if data.get("error"):
        body.append({"type": "TextBlock", "text": "📧 Gmail", "size": "Medium", "weight": "Bolder"})
        body.append({"type": "TextBlock", "text": str(data["error"]), "color": "Attention", "wrap": True})
        return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}

    emails = data.get("emails", [])
    email_type = data.get("type", "gmail")

    if email_type == "gmail_summary":
        # Summary view
        unread = data.get("unread_count", 0)
        body.append({"type": "TextBlock", "text": "📧 Gmail Summary", "size": "Medium", "weight": "Bolder"})
        body.append({"type": "ColumnSet", "columns": [
            {"type": "Column", "width": "auto", "items": [
                {"type": "TextBlock", "text": str(unread), "size": "ExtraLarge", "weight": "Bolder",
                 "color": "Attention" if unread > 0 else "Good"}
            ]},
            {"type": "Column", "width": "stretch", "verticalContentAlignment": "Center", "items": [
                {"type": "TextBlock", "text": "unread emails", "isSubtle": True}
            ]},
        ]})
        emails = data.get("latest_emails", [])

    elif not emails:
        title = data.get("title", "Gmail")
        body.append({"type": "TextBlock", "text": f"📧 {title}", "size": "Medium", "weight": "Bolder"})
        body.append({"type": "TextBlock", "text": data.get("message", "No emails found"), "isSubtle": True, "wrap": True})
        body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True})
        return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}

    else:
        # Dynamic title based on type
        title = data.get("title")
        if not title:
            if email_type == "gmail_latest":
                title = f"Latest ({data.get('count', len(emails))})"
            else:
                title = f"Unread ({data.get('count', len(emails))})"
        body.append({"type": "TextBlock", "text": f"📧 {title}", "size": "Medium", "weight": "Bolder"})

    for e in emails[:10]:
        from_name = e.get("from_name", e.get("from", "Unknown"))
        subject = e.get("subject", "")
        snippet = html_mod.unescape(e.get("snippet", ""))[:120]
        is_unread = e.get("unread", False)

        # Header row: sender + unread dot
        header_cols = []
        if is_unread:
            header_cols.append({"type": "Column", "width": "auto", "verticalContentAlignment": "Center", "items": [
                {"type": "TextBlock", "text": "●", "color": "Accent", "size": "Small", "spacing": "None"},
            ]})
        header_cols.append({"type": "Column", "width": "stretch", "items": [
            {"type": "TextBlock", "text": from_name, "weight": "Bolder", "size": "Small", "wrap": True,
             "color": "Accent" if is_unread else "Default"},
        ]})

        email_items: list[dict] = [
            {"type": "ColumnSet", "spacing": "None", "columns": header_cols},
        ]

        # Subject (skip if empty)
        if subject:
            email_items.append(
                {"type": "TextBlock", "text": subject, "wrap": True, "size": "Small", "spacing": "None",
                 "weight": "Bolder" if is_unread else "Default"},
            )

        # Snippet
        if snippet:
            email_items.append(
                {"type": "TextBlock", "text": snippet, "size": "Small", "isSubtle": True,
                 "wrap": True, "spacing": "None", "maxLines": 2},
            )

        body.append({
            "type": "Container", "style": "emphasis",
            "spacing": "Small", "separator": True,
            "items": email_items,
        })

    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True})
    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


def commits_card(data: dict) -> dict:
    """Fallback template for GitHub commits."""
    body = [
        {"type": "TextBlock", "text": "💻 Today's Commits", "size": "Large", "weight": "Bolder"},
        {"type": "TextBlock", "text": str(data.get("total", 0)), "size": "ExtraLarge",
         "weight": "Bolder", "color": "Good" if data.get("total", 0) > 0 else "Attention",
         "horizontalAlignment": "Center"},
        {"type": "TextBlock", "text": "commits today", "horizontalAlignment": "Center",
         "size": "Small", "isSubtle": True},
    ]

    if data.get("repos"):
        body.append({"type": "TextBlock", "text": "By repo:", "weight": "Bolder",
                      "spacing": "Medium", "separator": True})
        facts = [{"title": r["name"], "value": str(r["count"])} for r in data["repos"]]
        body.append({"type": "FactSet", "facts": facts})

    if data.get("last_commit") and data["last_commit"] != "No commits today":
        body.append({"type": "TextBlock", "text": f"Last: \"{data['last_commit']}\"",
                      "size": "Small", "isSubtle": True, "wrap": True, "spacing": "Small"})

    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


def weather_card(data: dict) -> dict:
    """Template for weather widget — shows temp, AQI, wind, humidity, cloud."""
    cities = data.get("cities", [])
    body: list[dict] = []

    for cd in cities:
        if cd.get("error"):
            body += [
                {"type": "TextBlock", "text": f"❌ {cd.get('city', 'Weather')}", "weight": "Bolder", "wrap": True},
                {"type": "TextBlock", "text": str(cd["error"]), "color": "Attention", "wrap": True, "size": "Small"},
            ]
            continue

        city_name = cd.get("city", "Weather")
        icon = cd.get("icon", "🌡️")
        temp_c = cd.get("temp_c", "?")
        feels = cd.get("feels_like_c", "?")
        condition = cd.get("condition", "")
        humidity = cd.get("humidity", "?")
        cloud = cd.get("cloud", "?")
        wind_kph = cd.get("wind_kph", cd.get("wind_mph", "?"))
        wind_dir = cd.get("wind_dir", "")
        uv = cd.get("uv_index", "?")
        aqi_label = cd.get("aqi_label", "N/A")
        aqi_color = cd.get("aqi_color", "Default")
        pm25 = cd.get("pm2_5", "?")
        pm10 = cd.get("pm10", "?")

        # ── Header: icon + temp + city ──
        body.append({
            "type": "ColumnSet", "spacing": "Small",
            "columns": [
                {"type": "Column", "width": "auto", "verticalContentAlignment": "Center", "items": [
                    {"type": "TextBlock", "text": icon, "size": "ExtraLarge"},
                ]},
                {"type": "Column", "width": "stretch", "items": [
                    {"type": "TextBlock", "text": f"{temp_c}°C", "size": "ExtraLarge", "weight": "Bolder", "spacing": "None"},
                    {"type": "TextBlock", "text": f"Feels like {feels}°C · {condition}", "size": "Small", "isSubtle": True, "spacing": "None", "wrap": True},
                ]},
                {"type": "Column", "width": "auto", "verticalContentAlignment": "Center", "items": [
                    {"type": "TextBlock", "text": city_name, "weight": "Bolder", "horizontalAlignment": "Right", "size": "Small"},
                    {"type": "TextBlock", "text": cd.get("localtime", "")[-5:] if cd.get("localtime") else "", "size": "Small", "isSubtle": True, "horizontalAlignment": "Right", "spacing": "None"},
                ]},
            ],
        })

        # ── Stats grid (2×2) ──
        body.append({
            "type": "ColumnSet", "spacing": "Medium",
            "columns": [
                {"type": "Column", "width": "stretch", "style": "emphasis", "items": [
                    {"type": "TextBlock", "text": "💧 Humidity", "size": "Small", "isSubtle": True, "spacing": "None"},
                    {"type": "TextBlock", "text": f"{humidity}%", "weight": "Bolder", "spacing": "None"},
                ]},
                {"type": "Column", "width": "stretch", "style": "emphasis", "items": [
                    {"type": "TextBlock", "text": "☁️ Cloud", "size": "Small", "isSubtle": True, "spacing": "None"},
                    {"type": "TextBlock", "text": f"{cloud}%", "weight": "Bolder", "spacing": "None"},
                ]},
                {"type": "Column", "width": "stretch", "style": "emphasis", "items": [
                    {"type": "TextBlock", "text": "💨 Wind", "size": "Small", "isSubtle": True, "spacing": "None"},
                    {"type": "TextBlock", "text": f"{wind_kph} km/h {wind_dir}", "weight": "Bolder", "spacing": "None", "wrap": True},
                ]},
            ],
        })

        # ── Air Quality row ──
        aqi_items: list[dict] = [
            {"type": "ColumnSet", "spacing": "None", "columns": [
                {"type": "Column", "width": "stretch", "items": [
                    {"type": "TextBlock", "text": "🫁 Air Quality", "size": "Small", "isSubtle": True, "spacing": "None"},
                    {"type": "TextBlock", "text": aqi_label, "weight": "Bolder", "color": aqi_color, "spacing": "None"},
                ]},
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": f"PM2.5: {pm25}", "size": "Small", "isSubtle": True, "spacing": "None"},
                    {"type": "TextBlock", "text": f"PM10: {pm10}", "size": "Small", "isSubtle": True, "spacing": "None"},
                ]},
            ]},
        ]
        body.append({"type": "Container", "style": "emphasis", "spacing": "Small", "items": aqi_items})

        # ── UV row ──
        if uv and uv != "?":
            body.append({
                "type": "TextBlock", "text": f"☀️ UV Index: {uv}", "size": "Small", "isSubtle": True, "spacing": "Small",
            })

    if not cities:
        body.append({"type": "TextBlock", "text": "No weather data", "isSubtle": True})

    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


def news_card(data: dict) -> dict:
    """Template for NewsData.io news feed widget."""
    import html as html_mod

    if data.get("error"):
        return _simple_card("📰 News", str(data["error"]))

    query = data.get("query") or data.get("topic")
    category = data.get("category")
    endpoint = data.get("endpoint", "latest")

    # Title
    if endpoint == "crypto":
        title = "🪙 Crypto News"
    elif endpoint == "market":
        title = "📈 Market News"
    elif query:
        title = f"📰 News: {query.title()}"
    elif category:
        title = f"📰 {category.title()} News"
    else:
        title = "📰 Latest News"

    body = [
        {"type": "TextBlock", "text": title, "size": "Large", "weight": "Bolder"},
    ]

    articles = data.get("articles", data.get("stories", []))

    for i, art in enumerate(articles[:8], 1):
        art_title = html_mod.unescape(art.get("title", "No title"))[:100]
        desc = html_mod.unescape(art.get("description", ""))[:120]
        source = art.get("source", "")
        published = art.get("published", "")[:10]
        image = art.get("image")
        url = art.get("url", "")
        cat = art.get("category", "")

        # Article container
        items = []

        # Source + category header row
        meta_parts = []
        if source:
            meta_parts.append(source)
        if cat:
            meta_parts.append(cat.upper())
        if published:
            meta_parts.append(published)
        if meta_parts:
            items.append({"type": "TextBlock", "text": " · ".join(meta_parts),
                          "size": "Small", "isSubtle": True, "spacing": "None"})

        # Title
        items.append({"type": "TextBlock", "text": f"**{art_title}**",
                       "size": "Small", "wrap": True, "spacing": "None"})

        # Description
        if desc:
            items.append({"type": "TextBlock", "text": desc,
                          "size": "Small", "isSubtle": True, "wrap": True, "spacing": "None"})

        container = {
            "type": "Container", "style": "emphasis",
            "items": items, "spacing": "Small",
        }
        if url:
            container["selectAction"] = {"type": "Action.OpenUrl", "url": url}

        body.append(container)

    if not articles:
        body.append({"type": "TextBlock", "text": "No articles found", "isSubtle": True})

    total = data.get("total", 0)
    footer = f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
    if total:
        footer += f" · {total} total results"
    body.append({"type": "TextBlock", "text": footer,
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


def system_health_card(data: dict) -> dict:
    """Template for system health/monitoring widget - AdaptiveCards 1.6 compliant."""
    
    def status_color(status: str) -> str:
        return {"good": "Good", "warning": "Warning", "critical": "Attention"}.get(status, "Default")
    
    cpu = data.get("cpu", {})
    mem = data.get("memory", {})
    disk = data.get("disk", {})
    battery = data.get("battery", {})
    
    # Build facts for FactSet
    facts = [
        {"title": "CPU", "value": f"{cpu.get('percent', 0)}% ({cpu.get('cores', 0)} cores)"},
        {"title": "RAM", "value": f"{mem.get('used_gb', 0):.1f} / {mem.get('total_gb', 0):.1f} GB ({mem.get('percent', 0)}%)"},
        {"title": "Disk", "value": f"{disk.get('free_gb', 0):.1f} GB free ({disk.get('percent', 0)}% used)"},
    ]
    
    if battery:
        plug_status = "Charging" if battery.get("plugged") else "On battery"
        facts.append({"title": "Battery", "value": f"{battery.get('percent', 0)}% - {plug_status}"})
    
    body = [
        {
            "type": "TextBlock",
            "text": "System Health",
            "size": "Large",
            "weight": "Bolder",
            "wrap": True
        },
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": f"{cpu.get('percent', 0)}%", "size": "ExtraLarge", "weight": "Bolder", "color": status_color(cpu.get('status', 'good')), "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "CPU", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": f"{mem.get('percent', 0)}%", "size": "ExtraLarge", "weight": "Bolder", "color": status_color(mem.get('status', 'good')), "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "RAM", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": f"{disk.get('percent', 0)}%", "size": "ExtraLarge", "weight": "Bolder", "color": status_color(disk.get('status', 'good')), "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "Disk", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                }
            ]
        },
        {
            "type": "FactSet",
            "facts": facts,
            "separator": True
        },
        {
            "type": "TextBlock",
            "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
            "size": "Small",
            "isSubtle": True,
            "spacing": "Medium",
            "wrap": True
        }
    ]
    
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body
    }


def github_activity_card(data: dict) -> dict:
    """Template for GitHub activity (PRs + commits) widget - AdaptiveCards 1.6 compliant."""
    summary = data.get("summary", {})
    prs = data.get("prs", {})
    
    body = [
        {
            "type": "TextBlock",
            "text": "GitHub Activity",
            "size": "Large",
            "weight": "Bolder",
            "wrap": True
        },
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": str(summary.get("commits_today", 0)), "size": "ExtraLarge", "weight": "Bolder", "color": "Good", "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "commits", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": str(summary.get("open_prs", 0)), "size": "ExtraLarge", "weight": "Bolder", "color": "Accent", "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "open PRs", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": str(summary.get("reviews_pending", 0)), "size": "ExtraLarge", "weight": "Bolder", "color": "Warning", "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "to review", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                }
            ]
        }
    ]
    
    # Open PRs as FactSet
    if prs.get("created"):
        body.append({"type": "TextBlock", "text": "Your PRs:", "weight": "Bolder", "spacing": "Medium", "separator": True, "wrap": True})
        pr_facts = [{"title": f"#{pr['number']}", "value": pr['title'][:40]} for pr in prs["created"][:3]]
        body.append({"type": "FactSet", "facts": pr_facts})
    
    body.append({
        "type": "TextBlock",
        "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
        "size": "Small",
        "isSubtle": True,
        "spacing": "Medium",
        "separator": True,
        "wrap": True
    })
    
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body
    }


def standup_card(data: dict) -> dict:
    """Template for daily standup prep widget."""
    body = [
        {"type": "TextBlock", "text": "📋 Standup Prep", "size": "Large", "weight": "Bolder"},
    ]
    
    # Yesterday section
    yesterday = data.get("yesterday", {})
    body.append({"type": "TextBlock", "text": f"Yesterday ({yesterday.get('count', 0)} commits)", "weight": "Bolder", "spacing": "Medium"})
    
    if yesterday.get("commits"):
        for commit in yesterday["commits"][:5]:
            body.append({"type": "TextBlock", "text": f"• [{commit['repo']}] {commit['message']}", "size": "Small", "wrap": True})
    else:
        body.append({"type": "TextBlock", "text": "No commits yesterday", "size": "Small", "isSubtle": True})
    
    # Today section
    today = data.get("today", {})
    body.append({"type": "TextBlock", "text": f"Today so far ({today.get('count', 0)} commits)", "weight": "Bolder", "spacing": "Medium", "separator": True})
    
    if today.get("commits"):
        for commit in today["commits"][:3]:
            body.append({"type": "TextBlock", "text": f"• [{commit['repo']}] {commit['message']}", "size": "Small", "wrap": True})
    else:
        body.append({"type": "TextBlock", "text": "No commits today yet", "size": "Small", "isSubtle": True})
    
    # PRs summary
    body.append({
        "type": "ColumnSet",
        "columns": [
            {"type": "Column", "width": "stretch", "items": [
                {"type": "TextBlock", "text": f"🔃 {data.get('open_prs', 0)} open PRs", "size": "Small"},
            ]},
            {"type": "Column", "width": "stretch", "items": [
                {"type": "TextBlock", "text": f"👀 {data.get('review_requested', 0)} reviews", "size": "Small"},
            ]},
        ],
        "spacing": "Medium",
        "separator": True,
    })
    
    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})
    
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


def prs_card(data: dict) -> dict:
    """Template for GitHub pull requests widget."""
    body = [
        {"type": "TextBlock", "text": "🔃 Pull Requests", "size": "Large", "weight": "Bolder"},
    ]
    
    # Summary
    body.append({
        "type": "ColumnSet",
        "columns": [
            {"type": "Column", "width": "stretch", "items": [
                {"type": "TextBlock", "text": str(data.get("total_created", 0)), "size": "ExtraLarge", "weight": "Bolder", "color": "Accent", "horizontalAlignment": "Center"},
                {"type": "TextBlock", "text": "your PRs", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center"},
            ]},
            {"type": "Column", "width": "stretch", "items": [
                {"type": "TextBlock", "text": str(data.get("total_review", 0)), "size": "ExtraLarge", "weight": "Bolder", "color": "Warning", "horizontalAlignment": "Center"},
                {"type": "TextBlock", "text": "to review", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center"},
            ]},
        ],
        "spacing": "Medium",
    })
    
    # Your PRs
    if data.get("created"):
        body.append({"type": "TextBlock", "text": "Your open PRs:", "weight": "Bolder", "spacing": "Medium", "separator": True})
        for pr in data["created"][:4]:
            pr_item = {
                "type": "Container",
                "items": [
                    {"type": "TextBlock", "text": pr['title'], "wrap": True, "size": "Small", "weight": "Bolder"},
                    {"type": "TextBlock", "text": f"{pr['repo']} #{pr['number']} • 💬 {pr.get('comments', 0)}", "size": "Small", "isSubtle": True},
                ],
                "spacing": "Small",
            }
            if pr.get("url"):
                pr_item["selectAction"] = {"type": "Action.OpenUrl", "url": pr["url"]}
            body.append(pr_item)
    
    # Reviews requested
    if data.get("review_requested"):
        body.append({"type": "TextBlock", "text": "Waiting for your review:", "weight": "Bolder", "spacing": "Medium", "separator": True})
        for pr in data["review_requested"][:3]:
            pr_item = {
                "type": "Container",
                "items": [
                    {"type": "TextBlock", "text": pr['title'], "wrap": True, "size": "Small"},
                    {"type": "TextBlock", "text": f"{pr['repo']} #{pr['number']}", "size": "Small", "isSubtle": True},
                ],
                "spacing": "Small",
            }
            if pr.get("url"):
                pr_item["selectAction"] = {"type": "Action.OpenUrl", "url": pr["url"]}
            body.append(pr_item)
    
    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})
    
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


def process_metrics_card(data: dict) -> dict:
    """Template for process-specific CPU/memory metrics - AdaptiveCards 1.6 compliant."""
    process_name = data.get("process_name", "Process")
    found = data.get("found", False)
    
    body = [
        {
            "type": "TextBlock",
            "text": f"{process_name.title()} Usage",
            "size": "Large",
            "weight": "Bolder",
            "wrap": True
        }
    ]
    
    if not found:
        body.append({
            "type": "TextBlock",
            "text": f"No processes matching '{process_name}' are currently running.",
            "wrap": True,
            "isSubtle": True
        })
    else:
        # Summary stats
        body.append({
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": f"{data.get('total_cpu_percent', 0)}%", "size": "ExtraLarge", "weight": "Bolder", "color": "Accent", "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "CPU", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": f"{data.get('total_memory_mb', 0):.0f}", "size": "ExtraLarge", "weight": "Bolder", "color": "Warning", "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "MB RAM", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {"type": "TextBlock", "text": str(data.get('process_count', 0)), "size": "ExtraLarge", "weight": "Bolder", "color": "Good", "horizontalAlignment": "Center"},
                        {"type": "TextBlock", "text": "Processes", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "wrap": True}
                    ]
                }
            ]
        })
        
        # Process list as FactSet
        processes = data.get("processes", [])[:5]
        if processes:
            body.append({"type": "TextBlock", "text": "Top processes:", "weight": "Bolder", "spacing": "Medium", "separator": True, "wrap": True})
            facts = [
                {"title": p['name'][:20], "value": f"{p['cpu_percent']}% CPU, {p['memory_mb']:.0f}MB"}
                for p in processes
            ]
            body.append({"type": "FactSet", "facts": facts})
    
    body.append({
        "type": "TextBlock",
        "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
        "size": "Small",
        "isSubtle": True,
        "spacing": "Medium",
        "separator": True,
        "wrap": True
    })
    
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body
    }


# ─── Stock Widget ──────────────────────────────────────────────

def stock_card(data: dict) -> dict:
    """Template for stock price widget - AdaptiveCards 1.6 compliant."""
    symbol = data.get("symbol", "???")
    found = data.get("found", False)
    
    body = [
        {"type": "TextBlock", "text": data.get("name", symbol), "size": "Medium", "weight": "Bolder", "wrap": True}
    ]
    
    if not found:
        body.append({"type": "TextBlock", "text": data.get("error", f"No data for {symbol}"), "wrap": True, "color": "Attention"})
    else:
        price = data.get("price", 0)
        change = data.get("change", 0)
        change_pct = data.get("change_percent", 0)
        is_up = change >= 0
        color = "Good" if is_up else "Attention"
        arrow = "▲" if is_up else "▼"
        
        body.extend([
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column", "width": "auto",
                        "items": [{"type": "TextBlock", "text": f"${price:,.2f}", "size": "ExtraLarge", "weight": "Bolder", "color": color}]
                    },
                    {
                        "type": "Column", "width": "stretch",
                        "items": [
                            {"type": "TextBlock", "text": f"{arrow} {abs(change):,.2f} ({abs(change_pct):.2f}%)", "color": color, "weight": "Bolder", "wrap": True},
                            {"type": "TextBlock", "text": data.get("market_state", ""), "size": "Small", "isSubtle": True, "wrap": True}
                        ]
                    }
                ]
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Symbol", "value": symbol},
                    {"title": "Exchange", "value": data.get("exchange", "")},
                    {"title": "Prev Close", "value": f"${data.get('previous_close', 0):,.2f}"},
                ],
                "separator": True
            }
        ])
    
    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True})
    
    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Counter Widget ───────────────────────────────────────────

def counter_card(data: dict) -> dict:
    """Template for counter widget."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": [
            {"type": "TextBlock", "text": data.get("title", "Counter"), "size": "Medium", "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": str(data.get("value", 0)), "size": "ExtraLarge", "weight": "Bolder", "horizontalAlignment": "Center", "color": "Accent"},
            {"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True}
        ],
        "actions": [
            {"type": "Action.Execute", "title": "+1", "verb": "increment"},
            {"type": "Action.Execute", "title": "-1", "verb": "decrement"},
            {"type": "Action.Execute", "title": "Reset", "verb": "reset"}
        ]
    }


# ─── Link / Bookmark Widget ───────────────────────────────────

def link_card(data: dict) -> dict:
    """Template for link/bookmark widget."""
    body = [
        {"type": "TextBlock", "text": data.get("title", "Link"), "size": "Medium", "weight": "Bolder", "wrap": True},
    ]
    if data.get("embed_url"):
        body.append({"type": "Image", "url": data["embed_url"], "size": "Stretch", "altText": "Preview"})
    body.extend([
        {"type": "TextBlock", "text": data.get("domain", ""), "size": "Small", "isSubtle": True, "wrap": True},
        {"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True}
    ])
    card = {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}
    if data.get("url"):
        card["actions"] = [{"type": "Action.OpenUrl", "title": "Open", "url": data["url"]}]
    return card


# ─── Checklist Widget ─────────────────────────────────────────

def checklist_card(data: dict) -> dict:
    """Template for checklist/to-do widget."""
    items = data.get("items", [])
    total = len(items)
    completed = sum(1 for i in items if i.get("done", False))
    
    body = [
        {"type": "TextBlock", "text": data.get("title", "Checklist"), "size": "Medium", "weight": "Bolder", "wrap": True},
        {"type": "TextBlock", "text": f"{completed}/{total} completed", "size": "Small", "isSubtle": True, "wrap": True},
    ]
    if items:
        facts = [{"title": ("✅" if i.get("done") else "⬜"), "value": i.get("text", "")} for i in items[:10]]
        body.append({"type": "FactSet", "facts": facts, "separator": True})
    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True})
    
    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Note Widget ──────────────────────────────────────────────

def note_card(data: dict) -> dict:
    """Template for note/reminder widget."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": [
            {"type": "TextBlock", "text": data.get("title", "Note"), "size": "Medium", "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": data.get("content", ""), "wrap": True},
            {"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True}
        ]
    }


# ─── Countdown Widget ─────────────────────────────────────────

def countdown_card(data: dict) -> dict:
    """Template for countdown/timer widget."""
    is_past = data.get("is_past", False)
    days = data.get("days_left", 0)
    hours = data.get("hours_left", 0)
    
    if is_past:
        text, color = "Event passed!", "Attention"
    elif days == 0:
        text, color = f"{hours}h left", "Warning"
    else:
        text = str(days)
        color = "Good" if days > 3 else "Warning" if days > 1 else "Attention"
    
    body = [
        {"type": "TextBlock", "text": data.get("title", "Countdown"), "size": "Medium", "weight": "Bolder", "wrap": True},
        {"type": "TextBlock", "text": text, "size": "ExtraLarge", "weight": "Bolder", "horizontalAlignment": "Center", "color": color},
    ]
    if not is_past and days > 0:
        body.append({"type": "TextBlock", "text": "days remaining", "horizontalAlignment": "Center", "isSubtle": True, "wrap": True})
    
    target = data.get("target_date", "")
    if target:
        try:
            dt = datetime.fromisoformat(target.replace("Z", "+00:00"))
            body.append({"type": "TextBlock", "text": f"Target: {dt.strftime('%b %d, %Y')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True})
        except (ValueError, TypeError):
            pass
    
    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Small", "wrap": True})
    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Tracker Widget ───────────────────────────────────────────

def tracker_card(data: dict) -> dict:
    """Template for generic tracker widget."""
    body = [{"type": "TextBlock", "text": data.get("title", "Tracker"), "size": "Medium", "weight": "Bolder", "wrap": True}]
    items = data.get("items", [])
    if items:
        facts = [{"title": i.get("label", "Item"), "value": str(i.get("value", 0))} for i in items[:8]]
        body.append({"type": "FactSet", "facts": facts})
    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}", "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True})
    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Timer Widget ──────────────────────────────────────────────

def timer_card(data: dict) -> dict:
    """Template for countdown timer widget (renders as live timer in frontend)."""
    total = data.get("total_seconds", 60)
    remaining = data.get("remaining_seconds", total)
    running = data.get("running", False)
    finished = data.get("finished", False)
    
    mins = remaining // 60
    secs = remaining % 60
    time_str = f"{mins:02d}:{secs:02d}"
    
    if finished:
        color = "Attention"
        status_text = "Time's up!"
    elif running:
        color = "Warning"
        status_text = "Running..."
    else:
        color = "Good"
        status_text = "Paused"
    
    body = [
        {"type": "TextBlock", "text": data.get("title", "Timer"), "size": "Medium", "weight": "Bolder", "wrap": True},
        {"type": "TextBlock", "text": time_str, "size": "ExtraLarge", "weight": "Bolder", "horizontalAlignment": "Center", "color": color},
        {"type": "TextBlock", "text": status_text, "horizontalAlignment": "Center", "isSubtle": True, "wrap": True},
    ]
    
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body
    }


# ─── Clock Widget ──────────────────────────────────────────────

def clock_card(data: dict) -> dict:
    """Template for clock widget (shows current time, updates in frontend)."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": [
            {"type": "TextBlock", "text": data.get("title", "Clock"), "size": "Medium", "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": data.get("time", "--:--:--"), "size": "ExtraLarge", "weight": "Bolder", "horizontalAlignment": "Center", "color": "Accent"},
            {"type": "TextBlock", "text": data.get("date", ""), "horizontalAlignment": "Center", "isSubtle": True, "wrap": True},
        ]
    }


# ─── Cricket Widget ────────────────────────────────────────────

# Format badge colors
_FMT_COLORS = {"T20": "Good", "ODI": "Accent", "TEST": "Warning"}


def cricket_card(data: dict) -> dict:
    """Template for cricket schedule / live scores."""
    body = [
        {"type": "TextBlock", "text": "\U0001F3CF  Cricket Schedule", "size": "Medium", "weight": "Bolder", "wrap": True},
    ]

    if data.get("error"):
        body.append({"type": "TextBlock", "text": data["error"], "color": "Attention", "wrap": True})
    else:
        matches = data.get("matches", [])
        if not matches:
            body.append({"type": "TextBlock", "text": "No upcoming matches found", "isSubtle": True, "wrap": True})

        shown_series: set = set()
        for m in matches[:8]:
            series = m.get("series", "")
            # Series header (only once per series)
            if series and series not in shown_series:
                shown_series.add(series)
                body.append({
                    "type": "TextBlock", "text": series,
                    "weight": "Bolder", "size": "Small", "color": "Accent",
                    "wrap": True, "spacing": "Medium", "separator": True,
                })

            t1 = m.get("team1", "TBC")
            t1s = m.get("team1_short", "")
            t2 = m.get("team2", "TBC")
            t2s = m.get("team2_short", "")
            fmt = m.get("format", "")
            desc = m.get("description", "")
            start = m.get("start", "")
            venue = m.get("venue", "")
            city = m.get("city", "")
            status = m.get("status", "")
            fmt_color = _FMT_COLORS.get(fmt, "Default")

            # ── match card (Container with emphasis style) ──
            match_items: list[dict] = []

            # Team matchup row: Team1  vs  Team2  [FORMAT]
            match_items.append({
                "type": "ColumnSet", "spacing": "Small",
                "columns": [
                    {"type": "Column", "width": "stretch", "items": [
                        {"type": "TextBlock", "text": t1, "weight": "Bolder",
                         "size": "Default", "horizontalAlignment": "Right", "wrap": True},
                    ]},
                    {"type": "Column", "width": "auto", "verticalContentAlignment": "Center", "items": [
                        {"type": "TextBlock", "text": "vs", "isSubtle": True,
                         "size": "Small", "horizontalAlignment": "Center"},
                    ]},
                    {"type": "Column", "width": "stretch", "items": [
                        {"type": "TextBlock", "text": t2, "weight": "Bolder",
                         "size": "Default", "wrap": True},
                    ]},
                    {"type": "Column", "width": "auto", "verticalContentAlignment": "Center", "items": [
                        {"type": "TextBlock", "text": fmt, "size": "Small",
                         "weight": "Bolder", "color": fmt_color},
                    ]} if fmt else {"type": "Column", "width": "auto", "items": []},
                ],
            })

            # Info line: description · start time
            info_parts = [p for p in [desc, start] if p]
            if info_parts:
                match_items.append({
                    "type": "TextBlock", "text": " · ".join(info_parts),
                    "size": "Small", "isSubtle": True, "wrap": True, "spacing": "None",
                })

            # Venue line
            if venue or city:
                loc = ", ".join(p for p in [venue, city] if p)
                match_items.append({
                    "type": "TextBlock", "text": f"📍 {loc}",
                    "size": "Small", "isSubtle": True, "wrap": True, "spacing": "None",
                })

            # Status (for live / completed matches)
            if status:
                match_items.append({
                    "type": "TextBlock", "text": status,
                    "size": "Small", "color": "Good", "wrap": True, "spacing": "None",
                })

            body.append({
                "type": "Container", "style": "emphasis",
                "spacing": "Small", "bleed": False,
                "items": match_items,
            })

    body.append({
        "type": "TextBlock",
        "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
        "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True, "wrap": True,
    })
    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Battery Health Card ──────────────────────────────────────

def battery_card(data: dict) -> dict:
    """Template for battery health widget with app consumption."""
    if data.get("error"):
        return _simple_card("🔋 Battery", data.get("message", str(data["error"])))

    pct = data.get("percent", 0)
    plugged = data.get("plugged", False)
    eta = data.get("eta", "")
    health = data.get("health_pct")
    cycles = data.get("cycle_count")

    # Icon based on level
    icon = "🔋" if pct > 30 else ("🪫" if pct > 10 else "⚠️")
    if plugged:
        icon = "🔌"

    pct_color = "Good" if pct > 50 else ("Warning" if pct > 20 else "Attention")

    body = [
        # Header: icon + percent + status
        {"type": "ColumnSet", "columns": [
            {"type": "Column", "width": "auto", "items": [
                {"type": "TextBlock", "text": icon, "size": "ExtraLarge"},
            ]},
            {"type": "Column", "width": "stretch", "verticalContentAlignment": "Center", "items": [
                {"type": "TextBlock", "text": f"{pct}%", "size": "ExtraLarge", "weight": "Bolder", "color": pct_color, "spacing": "None"},
                {"type": "TextBlock", "text": data.get("status", ""), "size": "Small", "isSubtle": True, "spacing": "None"},
            ]},
            {"type": "Column", "width": "auto", "verticalContentAlignment": "Center", "items": [
                {"type": "TextBlock", "text": eta, "size": "Medium", "weight": "Bolder", "horizontalAlignment": "Right"},
            ]},
        ]},
    ]

    # Health + Cycles row
    stat_cols = []
    if health is not None:
        stat_cols.append({"type": "Column", "width": "stretch", "style": "emphasis", "items": [
            {"type": "TextBlock", "text": f"{health}%", "weight": "Bolder", "horizontalAlignment": "Center",
             "color": "Good" if health > 70 else ("Warning" if health > 40 else "Attention")},
            {"type": "TextBlock", "text": "Health", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "spacing": "None"},
        ]})
    if cycles is not None:
        stat_cols.append({"type": "Column", "width": "stretch", "style": "emphasis", "items": [
            {"type": "TextBlock", "text": str(cycles), "weight": "Bolder", "horizontalAlignment": "Center"},
            {"type": "TextBlock", "text": "Cycles", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "spacing": "None"},
        ]})
    stat_cols.append({"type": "Column", "width": "stretch", "style": "emphasis", "items": [
        {"type": "TextBlock", "text": "⚡" if plugged else "🔋", "weight": "Bolder", "horizontalAlignment": "Center"},
        {"type": "TextBlock", "text": "Plugged In" if plugged else "On Battery", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "spacing": "None"},
    ]})

    if stat_cols:
        body.append({"type": "ColumnSet", "columns": stat_cols, "spacing": "Medium"})

    # Top apps by resource consumption
    top_apps = data.get("top_apps", [])
    if top_apps:
        body.append({"type": "TextBlock", "text": "⚡ Top App Consumption", "weight": "Bolder",
                     "spacing": "Medium", "separator": True})
        for app in top_apps[:5]:
            score = app.get("score", 0)
            score_color = "Attention" if score > 20 else ("Warning" if score > 10 else "Default")
            body.append({"type": "Container", "style": "emphasis", "spacing": "Small", "items": [
                {"type": "ColumnSet", "columns": [
                    {"type": "Column", "width": "stretch", "items": [
                        {"type": "TextBlock", "text": app.get("name", "?"), "weight": "Bolder", "size": "Small"},
                    ]},
                    {"type": "Column", "width": "auto", "items": [
                        {"type": "TextBlock", "text": f"CPU {app.get('cpu', 0)}%  MEM {app.get('memory', 0)}%",
                         "size": "Small", "isSubtle": True},
                    ]},
                    {"type": "Column", "width": "auto", "items": [
                        {"type": "TextBlock", "text": f"{score}%", "weight": "Bolder", "color": score_color},
                    ]},
                ]},
            ]})

    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Clipboard History Card ───────────────────────────────────

def clipboard_card(data: dict) -> dict:
    """Template for clipboard history — renders as custom widget in frontend."""
    if data.get("error"):
        return _simple_card("📋 Clipboard", str(data["error"]))

    # Return a special card the frontend will render with interactivity
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": [{"type": "TextBlock", "text": "Loading clipboard..."}],
        "_clipboard": {
            "items": data.get("items", []),
            "count": data.get("count", 0),
        },
    }


# ─── My Day Dashboard Card ────────────────────────────────────

def my_day_card(data: dict) -> dict:
    """Composite dashboard: calendar + gmail + weather + checklists."""
    now = datetime.now()
    greeting = "Good morning" if now.hour < 12 else ("Good afternoon" if now.hour < 17 else "Good evening")
    day_str = now.strftime("%A, %B %d")

    body = [
        {"type": "TextBlock", "text": f"☀️ {greeting}", "size": "Large", "weight": "Bolder"},
        {"type": "TextBlock", "text": day_str, "isSubtle": True, "spacing": "None"},
    ]

    # Weather one-liner
    weather_data = data.get("weather")
    if weather_data and not weather_data.get("error"):
        # Weather connector returns {"cities": [...], "count": N} — unwrap first city
        cities = weather_data.get("cities", [])
        w = cities[0] if cities else weather_data
        temp = w.get("temp_c", "")
        cond = w.get("condition", "")
        city = w.get("city", "Hyderabad")
        icon = w.get("condition_icon", "")
        if temp and cond:
            body.append({"type": "Container", "style": "emphasis", "spacing": "Medium", "items": [
                {"type": "ColumnSet", "columns": [
                    {"type": "Column", "width": "auto", "items": [
                        {"type": "Image", "url": icon, "size": "Small", "width": "32px"} if icon else
                        {"type": "TextBlock", "text": "🌤️"},
                    ]},
                    {"type": "Column", "width": "stretch", "verticalContentAlignment": "Center", "items": [
                        {"type": "TextBlock", "text": f"{temp}°C · {cond} · {city}", "size": "Default", "wrap": True},
                    ]},
                ]},
            ]})

    # Calendar events
    meetings = data.get("calendar", {}).get("meetings", [])
    if meetings:
        body.append({"type": "TextBlock", "text": "📅 Today's Schedule", "weight": "Bolder", "spacing": "Medium", "separator": True})
        for m in meetings[:4]:
            body.append({"type": "Container", "style": "emphasis", "spacing": "Small", "items": [
                {"type": "ColumnSet", "columns": [
                    {"type": "Column", "width": "auto", "items": [
                        {"type": "TextBlock", "text": m.get("start", "")[:5], "weight": "Bolder", "size": "Small", "color": "Accent"},
                    ]},
                    {"type": "Column", "width": "stretch", "items": [
                        {"type": "TextBlock", "text": m.get("subject", "Event"), "weight": "Bolder", "size": "Small", "wrap": True},
                    ]},
                ]},
            ]})
    else:
        body.append({"type": "TextBlock", "text": "📅 No meetings today 🎉", "isSubtle": True, "spacing": "Medium"})

    # Gmail unread
    gmail_data = data.get("gmail", {})
    unread = gmail_data.get("unread_count", 0)
    emails = gmail_data.get("emails", [])
    if unread > 0 or emails:
        body.append({"type": "TextBlock", "text": f"📧 {unread} unread email{'s' if unread != 1 else ''}", "weight": "Bolder",
                     "spacing": "Medium", "separator": True, "color": "Attention" if unread > 5 else "Default"})
        for e in emails[:3]:
            subj = e.get("subject", "(no subject)")[:50]
            sender = e.get("from", "")
            body.append({"type": "TextBlock", "text": f"• **{subj}** — {sender}", "size": "Small", "wrap": True})
    elif not gmail_data.get("error"):
        body.append({"type": "TextBlock", "text": "📧 Inbox zero! 🎉", "isSubtle": True, "spacing": "Medium"})

    body.append({"type": "TextBlock", "text": f"Updated: {now.strftime('%H:%M')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Disk Space Card ──────────────────────────────────────────

def disk_space_card(data: dict) -> dict:
    """Template for disk space monitor."""
    from urllib.parse import quote
    if data.get("error"):
        return _simple_card("💾 Disk Space", str(data["error"]))

    body = [
        {"type": "TextBlock", "text": "💾 Disk Space", "size": "Large", "weight": "Bolder"},
    ]

    # Drives
    drives = data.get("drives", [])
    for d in drives:
        pct = d.get("percent", 0)
        color = "Good" if pct < 70 else ("Warning" if pct < 90 else "Attention")
        mountpoint = d.get("mountpoint", d.get("drive", "C:\\"))
        encoded_path = quote(mountpoint, safe="")
        body.append({"type": "Container", "style": "emphasis", "spacing": "Small",
            "selectAction": {"type": "Action.OpenUrl", "url": f"http://localhost:8000/api/widgets/open?path={encoded_path}"},
            "items": [
            {"type": "ColumnSet", "columns": [
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": d.get("drive", "?"), "weight": "Bolder", "size": "Default"},
                ]},
                {"type": "Column", "width": "stretch", "items": [
                    {"type": "TextBlock", "text": f"{d.get('used_gb', 0)} / {d.get('total_gb', 0)} GB",
                     "size": "Small", "isSubtle": True, "horizontalAlignment": "Right"},
                ]},
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": f"{pct}%", "weight": "Bolder", "color": color},
                ]},
            ]},
        ]})

    # Temp + Recycle Bin
    temp_mb = data.get("temp_size_mb", 0)
    recycle_mb = data.get("recycle_size_mb")
    cleanup_items = []
    if temp_mb > 10:
        cleanup_items.append({"label": "Temp Files", "value": f"{temp_mb} MB"})
    if recycle_mb is not None and recycle_mb > 1:
        cleanup_items.append({"label": "Recycle Bin", "value": f"{recycle_mb} MB"})

    if cleanup_items:
        body.append({"type": "TextBlock", "text": "🧹 Cleanup Opportunities", "weight": "Bolder", "spacing": "Medium", "separator": True})
        cols = []
        for c in cleanup_items[:2]:
            cols.append({"type": "Column", "width": "stretch", "style": "emphasis", "items": [
                {"type": "TextBlock", "text": c["value"], "weight": "Bolder", "horizontalAlignment": "Center", "color": "Warning"},
                {"type": "TextBlock", "text": c["label"], "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "spacing": "None"},
            ]})
        body.append({"type": "ColumnSet", "columns": cols})

    # Biggest files in Downloads
    big_folders = data.get("big_folders", [])
    for bf in big_folders:
        items = bf.get("items", [])
        if items:
            folder_path = items[0].get("path", "")
            parent_path = ""
            if folder_path:
                import os
                from urllib.parse import quote
                parent_path = os.path.dirname(folder_path)

            header_item = {"type": "Container", "spacing": "Medium", "separator": True,
                "items": [{"type": "TextBlock", "text": f"📂 {bf['location']} (top items)", "weight": "Bolder", "size": "Small"}]}
            if parent_path:
                header_item["selectAction"] = {"type": "Action.OpenUrl",
                    "url": f"http://localhost:8000/api/widgets/open?path={quote(parent_path, safe='')}"}
            body.append(header_item)

            for item in items[:4]:
                icon = "📁" if item.get("is_dir") else "📄"
                file_container = {
                    "type": "Container", "spacing": "None",
                    "items": [{"type": "TextBlock", "text": f"{icon} {item['name'][:30]} — {item['size_mb']} MB",
                               "size": "Small", "wrap": True, "color": "Accent"}],
                }
                if item.get("path"):
                    file_container["selectAction"] = {"type": "Action.OpenUrl",
                        "url": f"http://localhost:8000/api/widgets/open?path={quote(item['path'], safe='')}"}
                body.append(file_container)

    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Network Monitor Card ─────────────────────────────────────

def network_card(data: dict) -> dict:
    """Template for network monitor widget."""
    if data.get("error"):
        return _simple_card("🌐 Network", str(data["error"]))

    body = []

    quality = data.get("quality", "Unknown")
    q_color = {"Good": "Good", "Fair": "Warning", "Poor": "Attention", "Offline": "Attention"}.get(quality, "Default")
    ping = data.get("ping_ms")
    wifi = data.get("wifi_name")
    conn_type = data.get("connection_type", "")

    # Header
    body.append({"type": "ColumnSet", "columns": [
        {"type": "Column", "width": "auto", "items": [
            {"type": "TextBlock", "text": "🌐", "size": "ExtraLarge"},
        ]},
        {"type": "Column", "width": "stretch", "verticalContentAlignment": "Center", "items": [
            {"type": "TextBlock", "text": wifi or conn_type, "size": "Medium", "weight": "Bolder", "spacing": "None"},
            {"type": "TextBlock", "text": f"{quality} · {ping}ms" if ping else quality,
             "size": "Small", "isSubtle": True, "color": q_color, "spacing": "None"},
        ]},
        {"type": "Column", "width": "auto", "verticalContentAlignment": "Center", "items": [
            {"type": "TextBlock", "text": f"{'📶 ' + str(data.get('signal_pct', '')) + '%' if data.get('signal_pct') else ''}",
             "size": "Small", "horizontalAlignment": "Right"},
        ]},
    ]})

    # Speed stats
    down = data.get("download_kbps", 0)
    up = data.get("upload_kbps", 0)
    down_str = f"{round(down/1024, 1)} MB/s" if down > 1024 else f"{down} KB/s"
    up_str = f"{round(up/1024, 1)} MB/s" if up > 1024 else f"{up} KB/s"

    body.append({"type": "ColumnSet", "spacing": "Medium", "columns": [
        {"type": "Column", "width": "stretch", "style": "emphasis", "items": [
            {"type": "TextBlock", "text": f"↓ {down_str}", "weight": "Bolder", "color": "Accent", "horizontalAlignment": "Center"},
            {"type": "TextBlock", "text": "Download", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "spacing": "None"},
        ]},
        {"type": "Column", "width": "stretch", "style": "emphasis", "items": [
            {"type": "TextBlock", "text": f"↑ {up_str}", "weight": "Bolder", "color": "Warning", "horizontalAlignment": "Center"},
            {"type": "TextBlock", "text": "Upload", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "spacing": "None"},
        ]},
        {"type": "Column", "width": "stretch", "style": "emphasis", "items": [
            {"type": "TextBlock", "text": f"{ping} ms" if ping else "—", "weight": "Bolder", "horizontalAlignment": "Center",
             "color": "Good" if ping and ping < 50 else ("Warning" if ping and ping < 100 else "Attention")},
            {"type": "TextBlock", "text": "Ping", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center", "spacing": "None"},
        ]},
    ]})

    # Session totals
    body.append({"type": "Container", "style": "emphasis", "spacing": "Medium", "items": [
        {"type": "ColumnSet", "columns": [
            {"type": "Column", "width": "stretch", "items": [
                {"type": "TextBlock", "text": f"↓ {data.get('total_recv_mb', 0)} MB", "size": "Small"},
            ]},
            {"type": "Column", "width": "stretch", "items": [
                {"type": "TextBlock", "text": f"↑ {data.get('total_sent_mb', 0)} MB", "size": "Small", "horizontalAlignment": "Right"},
            ]},
        ]},
        {"type": "TextBlock", "text": "Session totals (since boot)", "size": "Small", "isSubtle": True, "spacing": "None"},
    ]})

    # IP + ISP
    if data.get("public_ip"):
        body.append({"type": "TextBlock", "text": f"IP: {data['public_ip']}  ·  {data.get('isp', '')}",
                     "size": "Small", "isSubtle": True, "spacing": "Small"})

    body.append({"type": "TextBlock", "text": f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Google Search Card ────────────────────────────────────────

def search_card(data: dict) -> dict:
    """Template for Google Search results widget."""
    import html as html_mod

    if data.get("error"):
        return _simple_card("🔍 Search", str(data["error"]))

    query = data.get("query", "")
    body = [
        {"type": "TextBlock", "text": f"🔍 {query}", "size": "Large", "weight": "Bolder"},
    ]

    # Knowledge Graph (info box at top)
    kg = data.get("knowledge_graph")
    if kg and kg.get("title"):
        kg_items = [
            {"type": "TextBlock", "text": f"**{kg['title']}**", "size": "Medium", "wrap": True},
        ]
        if kg.get("type"):
            kg_items.append({"type": "TextBlock", "text": kg["type"], "size": "Small", "isSubtle": True, "spacing": "None"})
        if kg.get("description"):
            kg_items.append({"type": "TextBlock", "text": kg["description"][:250], "size": "Small", "wrap": True, "spacing": "Small"})

        # Key facts
        facts = kg.get("facts", {})
        if facts:
            fact_items = []
            for k, v in list(facts.items())[:5]:
                fact_items.append({"type": "TextBlock", "text": f"**{k}:** {v}", "size": "Small", "wrap": True, "spacing": "None"})
            kg_items.extend(fact_items)

        container = {"type": "Container", "style": "emphasis", "spacing": "Small", "items": kg_items}
        if kg.get("url"):
            container["selectAction"] = {"type": "Action.OpenUrl", "url": kg["url"]}
        body.append(container)

    # Answer Box (featured snippet)
    ab = data.get("answer_box")
    if ab and ab.get("answer"):
        ab_items = []
        if ab.get("title"):
            ab_items.append({"type": "TextBlock", "text": f"**{ab['title']}**", "size": "Small", "wrap": True})
        ab_items.append({"type": "TextBlock", "text": ab["answer"][:300], "size": "Small", "wrap": True, "color": "Accent"})
        container = {"type": "Container", "style": "emphasis", "spacing": "Small", "items": ab_items}
        if ab.get("url"):
            container["selectAction"] = {"type": "Action.OpenUrl", "url": ab["url"]}
        body.append(container)

    # Organic results
    results = data.get("results", [])
    for r in results[:6]:
        title = html_mod.unescape(r.get("title", ""))[:80]
        snippet = html_mod.unescape(r.get("snippet", ""))[:150]
        domain = r.get("domain", "")
        url = r.get("url", "")

        items = []
        if domain:
            items.append({"type": "TextBlock", "text": domain, "size": "Small", "isSubtle": True, "color": "Good", "spacing": "None"})
        items.append({"type": "TextBlock", "text": f"**{title}**", "size": "Small", "wrap": True, "spacing": "None"})
        if snippet:
            items.append({"type": "TextBlock", "text": snippet, "size": "Small", "isSubtle": True, "wrap": True, "spacing": "None"})

        container = {"type": "Container", "spacing": "Small", "items": items}
        if url:
            container["selectAction"] = {"type": "Action.OpenUrl", "url": url}
        body.append(container)

    if not results and not kg and not ab:
        body.append({"type": "TextBlock", "text": "No results found", "isSubtle": True})

    # Footer
    total = data.get("total_results", 0)
    time_taken = data.get("time_taken", "")
    footer = f"Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
    if total:
        footer += f" · ~{total:,} results"
    if time_taken:
        footer += f" ({time_taken})"
    body.append({"type": "TextBlock", "text": footer,
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
    }


# ─── Plane.so Card ─────────────────────────────────────────────

def plane_card(data: dict) -> dict:
    """Template for Plane.so issues widget."""
    if data.get("error"):
        return _simple_card("✈️ Plane", data.get("message", str(data["error"])))

    body = [
        {"type": "TextBlock", "text": "✈️ Plane Issues", "size": "Large", "weight": "Bolder"},
    ]

    issues = data.get("issues", [])
    priority_colors = {
        "urgent": "Attention", "high": "Warning",
        "medium": "Accent", "low": "Good", "none": "Default",
    }

    for issue in issues[:8]:
        name = issue.get("name", "Untitled")
        state = issue.get("state", "")
        priority = issue.get("priority", "none")
        assignees = ", ".join(issue.get("assignees", []))
        p_color = priority_colors.get(priority, "Default")

        items = [
            {"type": "ColumnSet", "columns": [
                {"type": "Column", "width": "stretch", "items": [
                    {"type": "TextBlock", "text": f"**{name}**", "size": "Small", "wrap": True, "spacing": "None"},
                ]},
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": priority.upper() if priority != "none" else "—",
                     "size": "Small", "color": p_color, "weight": "Bolder"},
                ]},
            ]},
        ]

        meta_parts = []
        if state:
            meta_parts.append(state)
        if assignees:
            meta_parts.append(assignees)
        if meta_parts:
            items.append({"type": "TextBlock", "text": " · ".join(meta_parts),
                          "size": "Small", "isSubtle": True, "spacing": "None"})

        body.append({"type": "Container", "style": "emphasis", "spacing": "Small", "items": items})

    if not issues:
        body.append({"type": "TextBlock", "text": "No issues found", "isSubtle": True})

    body.append({"type": "TextBlock",
                 "text": f"Workspace: {data.get('workspace', '')} · Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
                 "size": "Small", "isSubtle": True, "spacing": "Medium", "separator": True})

    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6", "body": body}


# ─── Credential Setup Card ─────────────────────────────────────

def credential_setup_card(state_info: dict) -> dict:
    """
    Renders a setup card when a widget is UNCONFIGURED.
    Shows what credentials are needed and how to get them.
    The frontend renders this with input fields for credential entry.
    """
    manifest = state_info.get("manifest", {})
    missing = state_info.get("missing", [])
    widget_name = manifest.get("name", "Widget")
    data_source = manifest.get("id", "")

    body = [
        {"type": "TextBlock", "text": f"🔧 {widget_name} — Setup Required",
         "size": "Large", "weight": "Bolder"},
        {"type": "TextBlock",
         "text": "This widget needs API credentials to fetch data. Follow the steps below to configure it.",
         "wrap": True, "isSubtle": True, "spacing": "Small"},
    ]

    for cap in missing:
        service = cap.get("service_name", "Service")
        setup_url = cap.get("setup_url", "")
        steps = cap.get("setup_steps", [])

        body.append({"type": "TextBlock", "text": f"**{service}**",
                     "size": "Medium", "spacing": "Medium", "separator": True})

        # Setup steps
        for i, step in enumerate(steps, 1):
            body.append({"type": "TextBlock", "text": f"{i}. {step}",
                         "size": "Small", "wrap": True, "spacing": "None"})

        if setup_url:
            body.append({"type": "ActionSet", "spacing": "Small", "actions": [
                {"type": "Action.OpenUrl", "title": f"Open {service}", "url": setup_url},
            ]})

    body.append({"type": "TextBlock",
                 "text": "Enter your credentials in the form below, then click Save.",
                 "wrap": True, "isSubtle": True, "spacing": "Medium", "separator": True})

    # Build the custom payload for the frontend to render input fields
    fields = []
    for cap in missing:
        if cap.get("fields"):
            for f in cap["fields"]:
                fields.append({
                    "key": f["key"],
                    "label": f.get("label", f["key"]),
                    "placeholder": f.get("placeholder", ""),
                    "default": f.get("default", ""),
                })
        else:
            fields.append({
                "key": cap.get("config_key", ""),
                "label": cap.get("service_name", "API Key"),
                "placeholder": cap.get("placeholder", ""),
                "default": "",
            })

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.6",
        "body": body,
        # Custom payload for the frontend credential form
        "_credential_setup": {
            "data_source": data_source,
            "widget_name": widget_name,
            "fields": fields,
            "state": "unconfigured",
        },
    }


# ─── Helper ────────────────────────────────────────────────────

def _simple_card(title: str, message: str) -> dict:
    return {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.6",
        "body": [
            {"type": "TextBlock", "text": title, "size": "Medium", "weight": "Bolder"},
            {"type": "TextBlock", "text": message, "wrap": True, "isSubtle": True},
        ],
    }