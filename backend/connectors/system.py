"""
System Health connector using psutil for local system metrics.
Provides CPU, RAM, disk, battery, network, and disk space stats.
"""
import psutil
import os
import subprocess
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

def get_system_health() -> dict:
    """
    Get comprehensive system health metrics.
    
    Returns:
        dict with CPU, RAM, disk, battery, and network info
    """
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    
    # Memory
    mem = psutil.virtual_memory()
    
    # Disk
    disk = psutil.disk_usage('/')
    
    # Battery (if available)
    battery = None
    try:
        batt = psutil.sensors_battery()
        if batt:
            battery = {
                "percent": batt.percent,
                "plugged": batt.power_plugged,
                "time_left": _format_time(batt.secsleft) if batt.secsleft > 0 else "Calculating..." if not batt.power_plugged else "Charging",
            }
    except:
        pass
    
    # Network (bytes sent/received since boot)
    net = psutil.net_io_counters()
    
    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": cpu_count,
            "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
            "status": _get_status(cpu_percent, thresholds=(50, 80)),
        },
        "memory": {
            "percent": mem.percent,
            "used_gb": round(mem.used / (1024**3), 1),
            "total_gb": round(mem.total / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "status": _get_status(mem.percent, thresholds=(60, 85)),
        },
        "disk": {
            "percent": disk.percent,
            "used_gb": round(disk.used / (1024**3), 1),
            "total_gb": round(disk.total / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "status": _get_status(disk.percent, thresholds=(70, 90)),
        },
        "battery": battery,
        "network": {
            "bytes_sent_mb": round(net.bytes_sent / (1024**2), 1),
            "bytes_recv_mb": round(net.bytes_recv / (1024**2), 1),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _get_status(value: float, thresholds: tuple = (50, 80)) -> str:
    """Get status indicator based on thresholds."""
    if value < thresholds[0]:
        return "good"
    elif value < thresholds[1]:
        return "warning"
    else:
        return "critical"


def _format_time(seconds: int) -> str:
    """Format seconds into human readable time."""
    if seconds < 0:
        return "Unknown"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def get_processes(count: int = 5) -> dict:
    """Get top processes by CPU and memory usage."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            pinfo = proc.info
            processes.append({
                "pid": pinfo['pid'],
                "name": pinfo['name'],
                "cpu_percent": pinfo['cpu_percent'] or 0,
                "memory_percent": round(pinfo['memory_percent'] or 0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Sort by CPU usage
    by_cpu = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:count]
    by_mem = sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:count]
    
    return {
        "top_cpu": by_cpu,
        "top_memory": by_mem,
    }


def get_process_metrics(process_name: str) -> dict:
    """
    Get CPU and memory usage for a specific process (or group of processes).
    Matches process names case-insensitively and supports partial matches.
    
    Args:
        process_name: Name of process to find (e.g., "chrome", "code", "python")
    
    Returns:
        dict with aggregated metrics for matching processes
    """
    process_name_lower = process_name.lower()
    
    # Common aliases
    aliases = {
        "chrome": ["chrome", "chromium", "google chrome"],
        "vscode": ["code", "code.exe", "visual studio code"],
        "vs code": ["code", "code.exe"],
        "firefox": ["firefox", "mozilla"],
        "edge": ["msedge", "microsoft edge"],
        "teams": ["teams", "ms-teams"],
        "slack": ["slack"],
        "spotify": ["spotify"],
        "discord": ["discord"],
    }
    
    # Expand aliases
    search_terms = [process_name_lower]
    for alias, terms in aliases.items():
        if process_name_lower in alias or alias in process_name_lower:
            search_terms.extend(terms)
    search_terms = list(set(search_terms))
    
    matching_processes = []
    total_cpu = 0
    total_memory = 0
    total_memory_mb = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
        try:
            pinfo = proc.info
            proc_name = (pinfo['name'] or '').lower()
            
            # Check if process matches any search term
            if any(term in proc_name for term in search_terms):
                cpu = pinfo['cpu_percent'] or 0
                mem_pct = pinfo['memory_percent'] or 0
                mem_mb = (pinfo['memory_info'].rss / (1024**2)) if pinfo.get('memory_info') else 0
                
                matching_processes.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'],
                    "cpu_percent": round(cpu, 1),
                    "memory_percent": round(mem_pct, 1),
                    "memory_mb": round(mem_mb, 1),
                })
                total_cpu += cpu
                total_memory += mem_pct
                total_memory_mb += mem_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Sort by CPU usage
    matching_processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
    
    return {
        "process_name": process_name,
        "found": len(matching_processes) > 0,
        "process_count": len(matching_processes),
        "total_cpu_percent": round(total_cpu, 1),
        "total_memory_percent": round(total_memory, 1),
        "total_memory_mb": round(total_memory_mb, 1),
        "processes": matching_processes[:10],  # Top 10 by CPU
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_installed_apps() -> dict:
    """
    Discover installed apps and running processes on the machine.
    Used to suggest relevant widget ideas to the user.
    """
    import subprocess
    
    # Get all currently running processes (unique names)
    running = set()
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name and not name.startswith('svchost') and not name.startswith('System'):
                running.add(name.replace('.exe', ''))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Categorize known apps
    categories = {
        "browsers": [],
        "productivity": [],
        "development": [],
        "communication": [],
        "media": [],
        "gaming": [],
        "creative": [],
        "other": [],
    }
    
    app_map = {
        # Browsers
        "chrome": ("Google Chrome", "browsers"),
        "msedge": ("Microsoft Edge", "browsers"),
        "firefox": ("Firefox", "browsers"),
        "brave": ("Brave Browser", "browsers"),
        "opera": ("Opera", "browsers"),
        # Productivity
        "WINWORD": ("Microsoft Word", "productivity"),
        "EXCEL": ("Microsoft Excel", "productivity"),
        "POWERPNT": ("Microsoft PowerPoint", "productivity"),
        "ONENOTE": ("Microsoft OneNote", "productivity"),
        "OUTLOOK": ("Microsoft Outlook", "productivity"),
        "Notion": ("Notion", "productivity"),
        "Obsidian": ("Obsidian", "productivity"),
        # Development
        "Code": ("VS Code", "development"),
        "devenv": ("Visual Studio", "development"),
        "idea64": ("IntelliJ IDEA", "development"),
        "pycharm64": ("PyCharm", "development"),
        "WindowsTerminal": ("Windows Terminal", "development"),
        "python": ("Python", "development"),
        "node": ("Node.js", "development"),
        "docker": ("Docker", "development"),
        "Postman": ("Postman", "development"),
        "GitHubDesktop": ("GitHub Desktop", "development"),
        # Communication
        "Teams": ("Microsoft Teams", "communication"),
        "ms-teams": ("Microsoft Teams", "communication"),
        "slack": ("Slack", "communication"),
        "Discord": ("Discord", "communication"),
        "Zoom": ("Zoom", "communication"),
        "Telegram": ("Telegram", "communication"),
        "WhatsApp": ("WhatsApp", "communication"),
        # Media
        "Spotify": ("Spotify", "media"),
        "vlc": ("VLC", "media"),
        "iTunes": ("iTunes", "media"),
        # Gaming
        "steam": ("Steam", "gaming"),
        "EpicGamesLauncher": ("Epic Games", "gaming"),
        "Battle.net": ("Battle.net", "gaming"),
        "Origin": ("Origin", "gaming"),
        "XboxApp": ("Xbox App", "gaming"),
        # Creative
        "Photoshop": ("Adobe Photoshop", "creative"),
        "Illustrator": ("Adobe Illustrator", "creative"),
        "Premiere Pro": ("Adobe Premiere Pro", "creative"),
        "AfterFX": ("Adobe After Effects", "creative"),
        "Figma": ("Figma", "creative"),
        "Blender": ("Blender", "creative"),
        "ScreenSketch": ("Snip & Sketch", "creative"),
    }
    
    detected_apps = []
    for proc_name in running:
        for key, (display_name, category) in app_map.items():
            if key.lower() in proc_name.lower():
                app_info = {"name": display_name, "process": proc_name, "category": category}
                if app_info not in categories[category]:
                    categories[category].append(app_info)
                    detected_apps.append(app_info)
                break
    
    # Also try to read installed programs from registry (Windows)
    installed_programs = []
    try:
        result = subprocess.run(
            ['powershell', '-Command', 
             'Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | '
             'Select-Object DisplayName | Where-Object {$_.DisplayName} | '
             'Sort-Object DisplayName | Select-Object -First 50 -ExpandProperty DisplayName'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            installed_programs = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
    except Exception:
        pass
    
    return {
        "running_apps": detected_apps,
        "running_count": len(detected_apps),
        "categories": {k: v for k, v in categories.items() if v},
        "installed_programs": installed_programs[:30],
        "all_running_processes": sorted(list(running))[:50],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Battery Health ────────────────────────────────────────────

# Track battery history for drain-rate estimation
_battery_history: list[tuple[float, float]] = []   # [(timestamp, percent), ...]

def get_battery_health() -> dict:
    """
    Detailed battery info: percent, drain/charge rate, time estimate,
    power mode, and health (via WMI on Windows).
    """
    global _battery_history
    try:
        batt = psutil.sensors_battery()
    except Exception:
        batt = None

    if not batt:
        return {"error": "no_battery", "message": "No battery detected — desktop PC?", "type": "battery"}

    now = time.time()
    pct = batt.percent
    plugged = batt.power_plugged

    # Track history (keep last 30 samples, ~60s apart)
    _battery_history.append((now, pct))
    if len(_battery_history) > 30:
        _battery_history = _battery_history[-30:]

    # Calculate drain / charge rate (%/hr)
    rate_pct_hr = None
    eta_display = None
    if len(_battery_history) >= 2:
        oldest_t, oldest_pct = _battery_history[0]
        dt_hrs = (now - oldest_t) / 3600.0
        if dt_hrs > 0.001:          # need at least ~4s of data
            delta_pct = pct - oldest_pct
            rate_pct_hr = round(delta_pct / dt_hrs, 1)

            if not plugged and rate_pct_hr < 0 and abs(rate_pct_hr) > 0.1:
                hrs_left = pct / abs(rate_pct_hr)
                eta_display = _format_time(int(hrs_left * 3600))
            elif plugged and rate_pct_hr > 0 and rate_pct_hr > 0.1:
                hrs_left = (100 - pct) / rate_pct_hr
                eta_display = _format_time(int(hrs_left * 3600))

    # Fallback to psutil's own estimate
    if eta_display is None:
        if batt.secsleft > 0:
            eta_display = _format_time(batt.secsleft)
        elif plugged:
            eta_display = "Fully charged" if pct >= 99 else "Charging…"
        else:
            eta_display = "Calculating…"

    # Power mode (Windows)
    power_mode = "Unknown"
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "(Get-CimInstance -Namespace root/cimv2/power -ClassName Win32_PowerPlan | Where-Object IsActive).ElementName"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            power_mode = r.stdout.strip()
    except Exception:
        pass

    # Battery health via WMI (design vs full-charge capacity)
    health_pct = None
    cycle_count = None
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance -Namespace root/WMI -ClassName BatteryFullChargedCapacity | Select -Exp FullChargedCapacity; "
             "Get-CimInstance -Namespace root/WMI -ClassName BatteryStaticData | Select -Exp DesignedCapacity; "
             "Get-CimInstance -Namespace root/WMI -ClassName BatteryCycleCount | Select -Exp CycleCount"],
            capture_output=True, text=True, timeout=8,
        )
        if r.returncode == 0:
            vals = [v.strip() for v in r.stdout.strip().split("\n") if v.strip()]
            if len(vals) >= 2:
                full_cap = int(vals[0])
                design_cap = int(vals[1])
                if design_cap > 0:
                    health_pct = min(round(full_cap / design_cap * 100, 1), 100)
            if len(vals) >= 3:
                cycle_count = int(vals[2])
    except Exception:
        pass

    status_label = "Charging" if plugged else "On battery"
    status_color = "Good" if pct > 30 else ("Warning" if pct > 15 else "Attention")

    # Top apps by resource consumption (CPU + Memory weighted)
    top_apps = []
    try:
        seen_names = set()
        app_usage = {}
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                name = (pinfo['name'] or '').replace('.exe', '')
                if not name or name.lower() in ('system', 'idle', 'registry', 'svchost',
                    'csrss', 'smss', 'wininit', 'services', 'lsass', 'conhost',
                    'dwm', 'fontdrvhost', 'ctfmon', 'searchhost', 'runtimebroker',
                    'taskhostw', 'sihost', 'explorer', 'startmenuexperiencehost',
                    'shellexperiencehost', 'textinputhost', 'applicationframehost',
                    'securityhealthsystray', 'sgrmbroker', 'spoolsv',
                    'searchindexer', 'msdtc', 'dllhost'):
                    continue
                cpu = pinfo['cpu_percent'] or 0
                mem = pinfo['memory_percent'] or 0
                if name in app_usage:
                    app_usage[name]['cpu'] += cpu
                    app_usage[name]['mem'] += mem
                    app_usage[name]['count'] += 1
                else:
                    app_usage[name] = {'cpu': cpu, 'mem': mem, 'count': 1}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Score by combined CPU + Memory impact
        scored = [(name, d['cpu'] + d['mem'], d['cpu'], d['mem'], d['count'])
                  for name, d in app_usage.items() if d['cpu'] + d['mem'] > 0.5]
        scored.sort(key=lambda x: x[1], reverse=True)

        for name, score, cpu, mem, count in scored[:6]:
            top_apps.append({
                "name": name,
                "score": round(score, 1),
                "cpu": round(cpu, 1),
                "memory": round(mem, 1),
                "processes": count,
            })
    except Exception:
        pass

    return {
        "type": "battery",
        "percent": pct,
        "plugged": plugged,
        "status": status_label,
        "status_color": status_color,
        "eta": eta_display,
        "rate_pct_hr": rate_pct_hr,
        "health_pct": health_pct,
        "cycle_count": cycle_count,
        "top_apps": top_apps,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Disk Space Monitor ───────────────────────────────────────

def get_disk_space() -> dict:
    """
    Per-drive usage + largest folders in Downloads/Temp + Recycle Bin size.
    """
    # Per-partition usage
    drives = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
            drives.append({
                "drive": part.device.rstrip("\\"),
                "mountpoint": part.mountpoint,
                "fs": part.fstype,
                "total_gb": round(u.total / (1024**3), 1),
                "used_gb": round(u.used / (1024**3), 1),
                "free_gb": round(u.free / (1024**3), 1),
                "percent": u.percent,
                "status": _get_status(u.percent, thresholds=(70, 90)),
            })
        except (PermissionError, OSError):
            pass

    # Largest folders inside Downloads & Temp
    big_folders = []
    scan_dirs = []
    home = Path.home()
    dl = home / "Downloads"
    if dl.exists():
        scan_dirs.append(("Downloads", dl))
    tmp = Path(os.environ.get("TEMP", ""))
    if tmp.exists():
        scan_dirs.append(("Temp", tmp))

    for label, folder in scan_dirs:
        try:
            entries = []
            for entry in folder.iterdir():
                try:
                    if entry.is_dir():
                        size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                    else:
                        size = entry.stat().st_size
                    entries.append({"name": entry.name, "size_mb": round(size / (1024**2), 1), "is_dir": entry.is_dir(), "path": str(entry)})
                except (PermissionError, OSError):
                    pass
            entries.sort(key=lambda x: x["size_mb"], reverse=True)
            big_folders.append({"location": label, "items": entries[:5]})
        except (PermissionError, OSError):
            pass

    # Temp folder total size
    temp_size_mb = 0.0
    try:
        for f in Path(os.environ.get("TEMP", "")).rglob("*"):
            try:
                if f.is_file():
                    temp_size_mb += f.stat().st_size
            except (PermissionError, OSError):
                pass
        temp_size_mb = round(temp_size_mb / (1024**2), 1)
    except Exception:
        pass

    # Recycle Bin size (Windows)
    recycle_size_mb = None
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "(New-Object -ComObject Shell.Application).NameSpace(10).Items() | "
             "Measure-Object -Property Size -Sum | Select -Exp Sum"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            recycle_size_mb = round(int(r.stdout.strip()) / (1024**2), 1)
    except Exception:
        pass

    return {
        "type": "disk_space",
        "drives": drives,
        "big_folders": big_folders,
        "temp_size_mb": temp_size_mb,
        "recycle_size_mb": recycle_size_mb,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Network Monitor ──────────────────────────────────────────

_net_snapshot: tuple[float, int, int] | None = None   # (time, sent, recv)

def get_network_monitor() -> dict:
    """
    Live network throughput, ping, WiFi info, public IP.
    """
    global _net_snapshot
    now = time.time()
    counters = psutil.net_io_counters()

    # If first call, take a 1-second sample to get real throughput
    if _net_snapshot is None:
        _net_snapshot = (now, counters.bytes_sent, counters.bytes_recv)
        time.sleep(1)
        now = time.time()
        counters = psutil.net_io_counters()

    # Throughput (delta since last snapshot)
    down_kbps = 0.0
    up_kbps = 0.0
    dt = now - _net_snapshot[0]
    if dt > 0.05:
        down_kbps = round((counters.bytes_recv - _net_snapshot[2]) / dt / 1024, 1)
        up_kbps = round((counters.bytes_sent - _net_snapshot[1]) / dt / 1024, 1)
    _net_snapshot = (now, counters.bytes_sent, counters.bytes_recv)

    # Ping google.com
    ping_ms = None
    try:
        start = time.time()
        s = socket.create_connection(("8.8.8.8", 53), timeout=3)
        ping_ms = round((time.time() - start) * 1000, 1)
        s.close()
    except Exception:
        pass

    # WiFi info (Windows)
    wifi_name = None
    signal_pct = None
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                l = line.strip()
                if l.startswith("SSID") and "BSSID" not in l:
                    wifi_name = l.split(":", 1)[1].strip()
                elif l.startswith("Signal"):
                    signal_pct = int(l.split(":", 1)[1].strip().replace("%", ""))
    except Exception:
        pass

    # Public IP (quick)
    public_ip = None
    isp = None
    try:
        import httpx
        resp = httpx.get("https://ipinfo.io/json", timeout=4)
        if resp.status_code == 200:
            j = resp.json()
            public_ip = j.get("ip")
            isp = j.get("org", "")
    except Exception:
        pass

    # Connection type
    conn_type = "WiFi" if wifi_name else "Wired"

    # Quality label
    quality = "Good"
    if ping_ms is None:
        quality = "Offline"
    elif ping_ms > 150:
        quality = "Poor"
    elif ping_ms > 60:
        quality = "Fair"

    return {
        "type": "network",
        "download_kbps": max(down_kbps, 0),
        "upload_kbps": max(up_kbps, 0),
        "ping_ms": ping_ms,
        "quality": quality,
        "wifi_name": wifi_name,
        "signal_pct": signal_pct,
        "connection_type": conn_type,
        "public_ip": public_ip,
        "isp": isp,
        "total_sent_mb": round(counters.bytes_sent / (1024**2), 1),
        "total_recv_mb": round(counters.bytes_recv / (1024**2), 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
