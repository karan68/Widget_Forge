# Widget Forge — Testing & Demo Flow Guide

## Table of Contents
1. [Prerequisites & Setup](#1-prerequisites--setup)
2. [Component-Level Testing](#2-component-level-testing)
3. [End-to-End User Flow](#3-end-to-end-user-flow)
4. [Demo Script (5 Widget Scenarios)](#4-demo-script-5-widget-scenarios)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. Prerequisites & Setup

### 1.1 Ollama Setup (Local LLM - Free)

1. **Install Ollama:** Download from https://ollama.ai/download
2. **Pull the Mistral model:**
   ```powershell
   ollama pull mistral
   ```
3. **Verify Ollama is running:**
   ```powershell
   ollama list
   # Should show: mistral:latest
   ```

### 1.2 Environment Configuration

1. **Your `.env` should contain:**
   ```env
   # LLM - Local Ollama (Free)
   OLLAMA_ENDPOINT=http://localhost:11434
   OLLAMA_MODEL=mistral

   # GitHub (Required for GitHub widgets)
   GITHUB_TOKEN=github_pat_...
   GITHUB_USERNAME=your_username
   ```

### 1.3 Install Dependencies

```powershell
cd "c:\Users\karanyadav\OneDrive - Microsoft\Desktop\side-work\Windows_hack\Widget_Forge"
.\venv\Scripts\activate
pip install -r requirements.txt
pip install psutil  # For system health widget
```

### 1.4 Start the Server

```powershell
cd "c:\Users\karanyadav\OneDrive - Microsoft\Desktop\side-work\Windows_hack\Widget_Forge"
.\venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 1.5 Open the Dashboard

Open **Microsoft Edge** and navigate to: `http://localhost:8000`

You should see the Widget Forge dashboard with:
- Header: "🔨 Widget Forge"
- Input box with placeholder text
- "Forge Widget" button
- Empty widget board

---

## 2. Component-Level Testing

### 2.1 Test Health Endpoint

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

**Expected:** `{"status": "ok", "service": "widget-forge"}`

### 2.2 Test Individual Connectors

#### System Health (No API required - instant)
```powershell
.\venv\Scripts\python -c "from backend.connectors.system import get_system_health; import json; print(json.dumps(get_system_health(), indent=2))"
```

**Expected:** JSON with CPU, memory, disk, battery info

#### Hacker News (Free API - no key)
```powershell
.\venv\Scripts\python -c "import asyncio; from backend.connectors.news import get_top_stories; print(asyncio.run(get_top_stories(5, 'AI')))"
```

**Expected:** JSON with 5 stories about AI

#### GitHub (Requires token)
```powershell
.\venv\Scripts\python -c "import asyncio; from backend.connectors.github import get_github_activity; import json; print(json.dumps(asyncio.run(get_github_activity()), indent=2))"
```

**Expected:** JSON with commits, PRs, and summary

### 2.3 Test LLM Intent Parser

Note: Local LLM takes 10-30 seconds to respond. Be patient!

```powershell
.\venv\Scripts\python -c "import asyncio; from backend.services.llm_service import parse_intent; import json; print(json.dumps(asyncio.run(parse_intent('Show me my system health')), indent=2))"
```

**Expected (after ~20 seconds):**
```json
{
  "data_source": "system",
  "data_type": "health",
  "title": "System Health",
  ...
}
```

**Expected:** JSON with `data_source: "ado"`, `data_type: "bugs"`, `grouping: "priority"`

### 2.4 Test Forge API Directly

```powershell
$body = '{"prompt": "Show me my system health"}'
Invoke-RestMethod -Uri "http://localhost:8000/api/widgets/forge" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120
```

**Expected:** Full widget object with `id`, `intent`, `adaptive_card`, `data`, `timing`

---

## 3. End-to-End User Flow

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User opens http://localhost:8000                            │
│         ↓                                                       │
│  2. User types natural language prompt in input box             │
│         ↓                                                       │
│  3. User clicks "Forge Widget" or presses Enter                 │
│         ↓                                                       │
│  4. Status shows "🔨 Parsing your intent..."                    │
│         ↓                                                       │
│  ┌─────────────────────────────────────────┐                   │
│  │         BACKEND PROCESSING              │                   │
│  │  a) Ollama LLM parses intent (10-30s)   │                   │
│  │  b) Data fetched from connector (1-5s)  │                   │
│  │  c) Ollama generates card (10-30s)      │                   │
│  │  d) Widget saved to store               │                   │
│  └─────────────────────────────────────────┘                   │
│         ↓                                                       │
│  5. Status shows "✨ Widget forged! Rendering..."               │
│         ↓                                                       │
│  6. Widget card appears on dashboard                            │
│         ↓                                                       │
│  7. User can Refresh or Delete widgets                          │
│         ↓                                                       │
│  8. Widgets persist — reload page, they reappear               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Supported Widgets

| Widget | Example Prompt | Data Source |
|--------|---------------|-------------|
| **System Health** | "Show my CPU, RAM, disk usage and battery" | Local (psutil) |
| **Hacker News** | "Show top 5 Hacker News posts about AI" | HN API (free) |
| **GitHub Activity** | "Show my open PRs and today's commits" | GitHub API |
| **GitHub PRs** | "Show my pull requests" | GitHub API |
| **Daily Standup** | "What did I work on yesterday?" | GitHub API |
| **Weather** | "Show weather for Seattle, Tokyo, London" | wttr.in (free) |

### Test Cases Checklist

| # | Test Case | Prompt | Expected Result | Pass? |
|---|-----------|--------|-----------------|-------|
| 1 | Page loads | - | Dashboard renders with input | ☐ |
| 2 | System Health | "Show me my system health" | Widget with CPU/RAM/disk gauges | ☐ |
| 3 | Hacker News | "Show top 5 Hacker News posts about AI" | Widget with 5 stories | ☐ |
| 4 | GitHub Activity | "Show my GitHub activity" | Widget with PRs + commits | ☐ |
| 5 | Standup Prep | "What did I work on yesterday?" | Widget with yesterday's commits | ☐ |
| 6 | Refresh widget | Click ↻ Refresh | Data updates | ☐ |
| 7 | Delete widget | Click ✕ | Widget removed | ☐ |
| 8 | Persistence | Refresh browser (F5) | Widgets reload | ☐ |

---

## 4. Demo Script (5 Widget Scenarios)

### Pre-Demo Preparation

1. **Ensure Ollama is running:**
   ```powershell
   ollama list  # Should show mistral:latest
   ```

2. **Start the server:**
   ```powershell
   .\venv\Scripts\activate
   uvicorn backend.main:app --reload --port 8000
   ```

3. **Clear widget board (fresh start):**
   ```powershell
   Set-Content -Path "backend\store\widgets.json" -Value "[]"
   ```

4. **Open browser:** http://localhost:8000

### Demo Script

---

#### **[0:00 - 0:15] Introduction**

Show the empty Widget Forge dashboard.

> "This is Widget Forge — an AI agent that creates live, data-connected Windows Widgets from natural language. Powered by a FREE local Ollama LLM — no cloud API costs!"

---

#### **[0:15 - 1:30] Demo 1: System Health Widget**

**Type in input box:**
```
Show me my CPU, RAM, disk usage and battery
```

**Click "Forge Widget"** (Wait ~30-60 seconds for local LLM)

**Point out in the widget:**
- CPU usage with visual gauge bar
- RAM usage (used/total GB)
- Disk space with color-coded status
- Battery status (if laptop)
- All data is LIVE from your actual machine!

> "In seconds, our local AI understood I wanted system metrics, gathered real data from this machine, and generated this beautiful widget — all from natural language."

---

#### **[1:30 - 2:30] Demo 2: Hacker News Feed (AI-filtered)**

**Type in input box:**
```
Show me top 5 Hacker News posts about AI
```

**Click "Forge Widget"**

**Point out in the widget:**
- 5 stories filtered by "AI" topic
- Upvote counts and comment counts
- Clickable links to full articles
- This is CUSTOM filtering that Windows widgets can't do!

> "Windows has a News widget — but try asking it for 'top AI stories from Hacker News'. It can't. Widget Forge can."

---

#### **[2:30 - 3:30] Demo 3: GitHub Activity**

**Type in input box:**
```
Show my open PRs and today's commits
```

**Click "Forge Widget"**

**Point out in the widget:**
- Commit count for today
- Open PR count
- Reviews pending count
- List of PR titles with repo names

> "Every developer wants this on their desktop. Nothing on Windows Widget Board does this. Widget Forge fills a real gap."

---

#### **[3:30 - 4:30] Demo 4: Daily Standup Prep**

**Type in input box:**
```
What did I work on yesterday? Check my git commits
```

**Click "Forge Widget"**

**Point out in the widget:**
- Yesterday's commits with repo names
- Today's commits (if any)
- Open PRs summary
- Perfect for standup meetings!

> "This solves a REAL daily pain point. Before every standup, developers scramble to remember what they did. This widget shows it instantly."

---

#### **[4:30 - 5:00] Demo 5: Refresh & Multiple Widgets**

Show all 4 widgets on screen.

**Click ↻ Refresh on the System Health widget**

> "Widgets can refresh on demand. Watch the CPU usage update live..."

Show all widgets side by side.

> "This is the power of Widget Forge — a personalized widget board created entirely through natural language. No code. No cloud costs. Just describe what you want."

---

#### **[5:00 - 5:15] Closing**

> "Widget Forge — democratizing Windows Widgets for every employee. One sentence. Live data. Powered by local AI."

---

## 5. Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Server won't start | Import errors | Run `pip install -r requirements.txt` and `pip install psutil` |
| Ollama not found | Connection refused | Run `ollama serve` or check Ollama is installed |
| LLM timeout | Forge takes > 120s | Normal for local LLM! Increase timeout or pre-warm |
| System health fails | psutil error | Run `pip install psutil` |
| GitHub 401 | Unauthorized | PAT expired — regenerate at github.com/settings/tokens |
| Hacker News slow | Takes 10+ seconds | API fetches each story individually — normal |
| Card render error | Red error in widget | Check browser console, use fallback template |
| Widgets don't persist | Gone after refresh | Check widgets.json has write permissions |
| JSON parse error | LLM returns invalid JSON | Fallback template will be used automatically |

### Debug Commands

```powershell
# Check server logs (visible in terminal running uvicorn)

# Check Ollama is running
ollama list

# Test System Health connector (instant, no API)
.\venv\Scripts\python -c "from backend.connectors.system import get_system_health; import json; print(json.dumps(get_system_health(), indent=2))"

# Test Hacker News connector
.\venv\Scripts\python -c "import asyncio; from backend.connectors.news import get_top_stories; import json; print(json.dumps(asyncio.run(get_top_stories(3)), indent=2))"

# Test GitHub connector
.\venv\Scripts\python -c "import asyncio; from backend.connectors.github import get_github_activity; import json; print(json.dumps(asyncio.run(get_github_activity()), indent=2))"

# Check widgets store
Get-Content backend\store\widgets.json | ConvertFrom-Json | Format-List

# Clear all widgets
Set-Content -Path "backend\store\widgets.json" -Value "[]"

# Test Ollama LLM connection (takes ~20 seconds)
.\venv\Scripts\python -c "import asyncio; from backend.services.llm_service import parse_intent; print(asyncio.run(parse_intent('test')))"
```

### API Test URLs

```
Health:     GET  http://localhost:8000/health
List:       GET  http://localhost:8000/api/widgets/list
Forge:      POST http://localhost:8000/api/widgets/forge
Refresh:    POST http://localhost:8000/api/widgets/refresh
Delete:     DELETE http://localhost:8000/api/widgets/{id}
```

---

## Quick Reference

### Five Magic Prompts (Demo)

1. **System Health:** `Show me my CPU, RAM, disk usage and battery`
2. **Hacker News:** `Show me top 5 Hacker News posts about AI`
3. **GitHub Activity:** `Show my open PRs and today's commits`
4. **Daily Standup:** `What did I work on yesterday?`
5. **GitHub PRs:** `Show my pull requests`

### Run Commands

```powershell
# Start Ollama (if not running)
ollama serve

# Activate environment
.\venv\Scripts\activate

# Start server
uvicorn backend.main:app --reload --port 8000

# Open dashboard
start http://localhost:8000
```

### Widget Types Summary

| Widget | Data Source | API Key Required? | Speed |
|--------|-------------|-------------------|-------|
| System Health | Local (psutil) | No | Instant |
| Hacker News | hn.algolia.com | No | 3-10s |
| GitHub Activity | GitHub API | Yes (token) | 5-10s |
| GitHub PRs | GitHub API | Yes (token) | 5-10s |
| Daily Standup | GitHub API | Yes (token) | 5-15s |
| Weather | wttr.in | No | 2-5s |

---

*Widget Forge — Describe a widget. Watch it appear. Powered by local AI.*
