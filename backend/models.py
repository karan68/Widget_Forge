from pydantic import BaseModel
from typing import Optional

class WidgetIntent(BaseModel):
    data_source: str         # "ado" | "google" | "github"
    data_type: str           # "bugs" | "meetings" | "commits" | "prs" | "builds"
    title: str               # Widget display title
    metrics: list[str]       # e.g., ["count_by_priority", "titles"]
    grouping: Optional[str]  # e.g., "priority", "repo", "time"
    count: Optional[int]     # e.g., 3 for "next 3 meetings"
    refresh_minutes: int     # suggested refresh interval
    layout: str              # "list" | "summary" | "chart"

class WidgetConfig(BaseModel):
    id: str
    prompt: str
    intent: WidgetIntent
    adaptive_card_json: dict
    created_at: str
    last_refreshed: Optional[str] = None
