const API_BASE = 'http://localhost:8000/api/widgets';

// Track active timers/intervals per widget
const activeTimers = {};

// ─── Completion-Based Auto Refresh with Lock ──────────────────
// Rule: never start a new refresh until the previous one finishes.
// Block all refreshes while a mutation (forge/delete) is running.

const _refreshState = {
    mutating: false,        // true while forge/delete/action is in-flight
    inflight: new Set(),    // widget IDs currently being refreshed
    intervals: {},          // per-widget refresh interval IDs
};

function _canRefresh(wid) {
    return !_refreshState.mutating && !_refreshState.inflight.has(wid);
}

async function _scheduledRefresh(wid) {
    if (!_canRefresh(wid)) return;          // skip this tick — previous still running or mutation in progress
    if (!document.getElementById(`widget-${wid}`)) {  // widget was deleted
        clearInterval(_refreshState.intervals[wid]);
        delete _refreshState.intervals[wid];
        return;
    }
    _refreshState.inflight.add(wid);
    try {
        const r = await fetch(`${API_BASE}/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ widget_id: wid }),
        });
        if (r.ok) renderWidget(await r.json());
    } catch (e) { /* silently skip — next tick will retry */ }
    finally { _refreshState.inflight.delete(wid); }
}

function _startAutoRefresh(widget) {
    const wid = widget.id;
    const mins = widget.refresh_minutes || 0;
    const state = widget.widget_state || '';
    // No auto-refresh for: no interval, unconfigured, degraded, or disabled widgets
    if (mins <= 0 || state === 'unconfigured' || state === 'degraded' || state === 'disabled') return;
    const ms = Math.max(mins * 60 * 1000, 10000);  // minimum 10 s
    if (_refreshState.intervals[wid]) clearInterval(_refreshState.intervals[wid]);
    _refreshState.intervals[wid] = setInterval(() => _scheduledRefresh(wid), ms);
}

function _stopAutoRefresh(wid) {
    if (_refreshState.intervals[wid]) {
        clearInterval(_refreshState.intervals[wid]);
        delete _refreshState.intervals[wid];
    }
}

async function forgeWidget() {
    const input = document.getElementById('prompt-input');
    const status = document.getElementById('status');
    const btn = document.getElementById('forge-btn');
    const prompt = input.value.trim();
    if (!prompt) return;

    btn.disabled = true;
    btn.textContent = 'Forging...';
    status.textContent = '🔨 Parsing your intent...';
    _refreshState.mutating = true;          // ━ lock: block all refreshes

    try {
        const response = await fetch(`${API_BASE}/forge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt }),
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Forge failed');
        }
        status.textContent = '✨ Widget forged!';
        const widget = await response.json();
        addWidgetToBoard(widget);
        input.value = '';
        setTimeout(() => { status.textContent = ''; }, 2000);
    } catch (error) {
        status.textContent = `❌ Error: ${error.message}`;
    } finally {
        _refreshState.mutating = false;     // ━ unlock
        btn.disabled = false;
        btn.textContent = 'Forge Widget';
    }
}

// Widget size classification
const WIDGET_SIZES = {
    // Small — compact, single-value widgets
    counter: 'sm', timer: 'sm', clock: 'sm', countdown: 'sm', note: 'sm',
    // Medium — standard info cards (default)
    weather: 'md', battery: 'md', network: 'md', stock: 'md',
    checklist: 'md', cricket: 'md', clipboard: 'md', link: 'md',
    tracker: 'md', price: 'md',
    // Large — rich content, multi-section widgets
    disk_space: 'lg', my_day: 'lg', gmail: 'lg', gmail_latest: 'lg',
    gmail_summary: 'lg', youtube: 'lg', health: 'lg',
    calendar: 'lg', meetings: 'lg',
    activity: 'lg', standup: 'lg', commits: 'lg', prs: 'lg',
    bugs: 'lg', work_items: 'lg', stories: 'lg', news: 'lg',
    latest: 'lg', crypto: 'lg', market: 'lg',
    search: 'lg', web: 'lg',
};

function getWidgetSize(widget) {
    const dtype = widget.data?.type || widget.intent?.data_type || '';
    const layout = widget.intent?.layout || '';
    return WIDGET_SIZES[dtype] || WIDGET_SIZES[layout] || 'md';
}

function addWidgetToBoard(widget) {
    const board = document.getElementById('widget-board');
    const card = document.createElement('div');
    const size = getWidgetSize(widget);
    card.className = `widget-card widget-${size}`;
    card.id = `widget-${widget.id}`;

    const source = widget.intent?.data_source?.toUpperCase() || '';
    const dataSource = widget.intent?.data_source || '';
    const widgetState = widget.widget_state || '';

    // State badge colors
    const stateBadge = widgetState === 'degraded' ? '<span class="state-badge degraded" title="API error — refresh paused">⚠️</span>'
        : widgetState === 'disabled' ? '<span class="state-badge disabled" title="Widget disabled">⏸️</span>'
        : widgetState === 'active' ? '<span class="state-badge active" title="Active">●</span>'
        : '';

    // Check if this widget type has credentials (to show reconfigure option)
    const hasCredentials = ['news','search','cricket','google','github','ado','plane','weather'].includes(dataSource);
    const isDisabled = widgetState === 'disabled';

    card.innerHTML = `
        <div class="widget-header">
            <span style="font-size:12px;color:#667eea;">${source} ${stateBadge}</span>
            <div class="widget-actions">
                <button onclick="refreshWidget('${widget.id}')" ${isDisabled ? 'disabled title="Widget disabled"' : ''}>↻</button>
                <button onclick="deleteWidget('${widget.id}')">✕</button>
                <div class="widget-menu-wrap">
                    <button class="widget-menu-btn" onclick="toggleWidgetMenu(event, '${widget.id}')">⋯</button>
                    <div class="widget-menu" id="menu-${widget.id}">
                        <div class="widget-menu-label">Size</div>
                        <button class="${size==='sm'?'active':''}" onclick="setWidgetSize('${widget.id}','sm')">Small</button>
                        <button class="${size==='md'?'active':''}" onclick="setWidgetSize('${widget.id}','md')">Medium</button>
                        <button class="${size==='lg'?'active':''}" onclick="setWidgetSize('${widget.id}','lg')">Large</button>
                        <div class="widget-menu-divider"></div>
                        <div class="widget-menu-label">State</div>
                        <button onclick="toggleWidget('${widget.id}', ${isDisabled})">${isDisabled ? '▶️ Enable' : '⏸️ Disable'}</button>
                        ${hasCredentials ? `
                        <div class="widget-menu-divider"></div>
                        <div class="widget-menu-label">Settings</div>
                        <button class="menu-reconfig" onclick="reconfigureWidget('${widget.id}')">🔑 Reconfigure</button>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
        <div class="widget-prompt">"${widget.prompt}"</div>
        <div class="widget-body" id="body-${widget.id}"></div>
    `;
    board.prepend(card);

    if (widget.timing) {
        card.querySelector('.widget-prompt').innerHTML += `<br>⚡ Forged in ${(widget.timing.total_ms / 1000).toFixed(1)}s`;
    }

    renderWidget(widget);

    // Start completion-based auto-refresh (respects the lock)
    _startAutoRefresh(widget);
}


// ─── Smart Widget Renderer ────────────────────────────────────

function renderWidget(widget) {
    const container = document.getElementById(`body-${widget.id}`);
    if (!container) return;

    // Check for credential setup card
    if (widget.adaptive_card?._credential_setup) {
        renderCredentialSetup(container, widget);
        return;
    }

    const data = widget.data || {};
    const widgetType = data.type || widget.intent?.data_type || '';

    switch (widgetType) {
        case 'counter':          renderCounter(container, widget); break;
        case 'timer':            renderTimer(container, widget); break;
        case 'clock':            renderClock(container, widget); break;
        case 'checklist':        renderChecklist(container, widget); break;
        case 'countdown':        renderCountdown(container, widget); break;
        case 'youtube':          renderYouTube(container, widget); break;
        case 'clipboard':        renderClipboard(container, widget); break;
        default:                 renderAdaptiveCard(widget.adaptive_card, container); break;
    }
}


// ─── Counter Widget ───────────────────────────────────────────

function renderCounter(container, widget) {
    const data = widget.data;
    container.innerHTML = `
        <div style="text-align:center;padding:20px 0;">
            <div style="font-size:16px;font-weight:bold;margin-bottom:12px;">${data.title || 'Counter'}</div>
            <div id="counter-val-${widget.id}" style="font-size:48px;font-weight:bold;color:#667eea;transition:transform .15s;">${data.value || 0}</div>
            <div style="margin-top:16px;display:flex;gap:8px;justify-content:center;">
                <button class="action-btn" onclick="counterAction('${widget.id}','decrement')">− 1</button>
                <button class="action-btn primary" onclick="counterAction('${widget.id}','increment')">+ 1</button>
                <button class="action-btn" onclick="counterAction('${widget.id}','reset')">Reset</button>
            </div>
        </div>
    `;
}

async function counterAction(widgetId, action) {
    try {
        const r = await fetch(`${API_BASE}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ widget_id: widgetId, action }),
        });
        const widget = await r.json();
        const el = document.getElementById(`counter-val-${widgetId}`);
        if (el) {
            el.textContent = widget.data.value;
            el.style.transform = 'scale(1.2)';
            setTimeout(() => el.style.transform = 'scale(1)', 150);
        }
    } catch (e) { console.error('Counter action failed:', e); }
}


// ─── Timer Widget ─────────────────────────────────────────────

function renderTimer(container, widget) {
    const data = widget.data;
    let remaining = data.remaining_seconds ?? data.total_seconds ?? 60;
    let total = data.total_seconds || 60;
    let running = false;

    function fmt(s) {
        const m = Math.floor(s / 60), sec = s % 60;
        return String(m).padStart(2,'0') + ':' + String(sec).padStart(2,'0');
    }
    function color(r, t) {
        const p = r / t;
        return p > 0.5 ? '#51cf66' : p > 0.2 ? '#ffd43b' : '#ff6b6b';
    }

    function draw() {
        const pct = Math.round((remaining / total) * 100);
        const c = color(remaining, total);
        const circ = 2 * Math.PI * 52;
        container.innerHTML = `
            <div style="text-align:center;padding:16px 0;">
                <div style="font-size:16px;font-weight:bold;margin-bottom:8px;">${data.title || 'Timer'}</div>
                <div style="position:relative;width:140px;height:140px;margin:0 auto;">
                    <svg width="140" height="140" viewBox="0 0 140 140">
                        <circle cx="70" cy="70" r="52" fill="none" stroke="#333" stroke-width="8"/>
                        <circle cx="70" cy="70" r="52" fill="none" stroke="${c}" stroke-width="8"
                            stroke-dasharray="${circ}" stroke-dashoffset="${circ * (1 - pct / 100)}"
                            transform="rotate(-90 70 70)" stroke-linecap="round" style="transition:stroke-dashoffset .3s;"/>
                    </svg>
                    <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:30px;font-weight:bold;color:${c};font-variant-numeric:tabular-nums;">
                        ${fmt(remaining)}
                    </div>
                </div>
                <div style="color:#888;font-size:12px;margin-top:4px;">${remaining <= 0 ? "⏰ Time's up!" : running ? '⏱ Running' : '⏸ Paused'}</div>
                <div style="margin-top:12px;display:flex;gap:8px;justify-content:center;">
                    <button class="action-btn ${running ? '' : 'primary'}" onclick="window._timerToggle_${widget.id.replace(/-/g,'_')}()">
                        ${running ? '⏸ Pause' : '▶ Start'}
                    </button>
                    <button class="action-btn" onclick="window._timerReset_${widget.id.replace(/-/g,'_')}()">↺ Reset</button>
                </div>
            </div>
        `;
    }
    draw();

    const sid = widget.id.replace(/-/g, '_');
    if (activeTimers[`timer-${widget.id}`]) clearInterval(activeTimers[`timer-${widget.id}`]);

    window[`_timerToggle_${sid}`] = () => {
        running = !running;
        if (running && remaining > 0) {
            activeTimers[`timer-${widget.id}`] = setInterval(() => {
                if (remaining > 0) {
                    remaining--;
                    draw();
                    if (remaining <= 0) {
                        running = false;
                        clearInterval(activeTimers[`timer-${widget.id}`]);
                        draw();
                        container.parentElement.style.boxShadow = '0 0 20px #ff6b6b';
                        setTimeout(() => container.parentElement.style.boxShadow = '', 3000);
                    }
                }
            }, 1000);
        } else {
            clearInterval(activeTimers[`timer-${widget.id}`]);
        }
        draw();
    };
    window[`_timerReset_${sid}`] = () => {
        running = false;
        clearInterval(activeTimers[`timer-${widget.id}`]);
        remaining = total;
        draw();
    };
}


// ─── Clock Widget ─────────────────────────────────────────────

function renderClock(container, widget) {
    function update() {
        const now = new Date();
        container.innerHTML = `
            <div style="text-align:center;padding:20px 0;">
                <div style="font-size:16px;font-weight:bold;margin-bottom:12px;">${widget.data?.title || 'Clock'}</div>
                <div style="font-size:42px;font-weight:bold;color:#667eea;font-variant-numeric:tabular-nums;">${now.toLocaleTimeString()}</div>
                <div style="color:#888;font-size:14px;margin-top:8px;">${now.toLocaleDateString([], {weekday:'long', year:'numeric', month:'long', day:'numeric'})}</div>
            </div>
        `;
    }
    update();
    if (activeTimers[`clock-${widget.id}`]) clearInterval(activeTimers[`clock-${widget.id}`]);
    activeTimers[`clock-${widget.id}`] = setInterval(update, 1000);
}


// ─── Checklist Widget ─────────────────────────────────────────

function renderChecklist(container, widget) {
    const data = widget.data;
    const items = data.items || [];
    const done = items.filter(i => i.done).length;

    let html = `<div style="padding:8px 0;">
        <div style="font-size:16px;font-weight:bold;margin-bottom:4px;">${data.title || 'Checklist'}</div>
        <div style="font-size:12px;color:#888;margin-bottom:8px;">${done}/${items.length} completed</div>
        <div style="max-height:240px;overflow-y:auto;">`;

    items.forEach((item, i) => {
        html += `<div style="display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px solid #2a2a3e;">
            <input type="checkbox" ${item.done ? 'checked' : ''} onchange="clToggle('${widget.id}',${i})" style="width:18px;height:18px;cursor:pointer;accent-color:#667eea;">
            <span style="flex:1;${item.done ? 'text-decoration:line-through;color:#555;' : 'color:#e0e0e0;'}">${item.text}</span>
            <button onclick="clRemove('${widget.id}',${i})" style="background:none;border:none;color:#ff6b6b;cursor:pointer;font-size:14px;">✕</button>
        </div>`;
    });

    html += `</div>
        <div style="display:flex;gap:8px;margin-top:10px;">
            <input type="text" id="cl-in-${widget.id}" placeholder="Add item..." 
                style="flex:1;padding:8px 10px;background:#12122a;border:1px solid #333;color:#e0e0e0;border-radius:6px;outline:none;"
                onkeydown="if(event.key==='Enter')clAdd('${widget.id}')">
            <button class="action-btn primary" onclick="clAdd('${widget.id}')">+ Add</button>
        </div>
    </div>`;
    container.innerHTML = html;
}

async function clToggle(wid, idx) {
    const r = await fetch(`${API_BASE}/action`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({widget_id:wid, action:'toggle', payload:{index:idx}}) });
    renderChecklist(document.getElementById(`body-${wid}`), await r.json());
}
async function clAdd(wid) {
    const inp = document.getElementById(`cl-in-${wid}`);
    const text = inp?.value?.trim();
    if (!text) return;
    const r = await fetch(`${API_BASE}/action`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({widget_id:wid, action:'add_item', payload:{text}}) });
    renderChecklist(document.getElementById(`body-${wid}`), await r.json());
}
async function clRemove(wid, idx) {
    const r = await fetch(`${API_BASE}/action`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({widget_id:wid, action:'remove_item', payload:{index:idx}}) });
    renderChecklist(document.getElementById(`body-${wid}`), await r.json());
}


// ─── Countdown Widget (live ticking) ──────────────────────────

function renderCountdown(container, widget) {
    const data = widget.data;
    function update() {
        const target = new Date(data.target_date);
        const diff = target - new Date();
        if (diff <= 0) {
            container.innerHTML = `<div style="text-align:center;padding:20px 0;">
                <div style="font-size:16px;font-weight:bold;">${data.title || 'Countdown'}</div>
                <div style="font-size:36px;font-weight:bold;color:#ff6b6b;margin:12px 0;">Event passed!</div>
            </div>`;
            return;
        }
        const d = Math.floor(diff / 86400000), h = Math.floor((diff % 86400000) / 3600000);
        const m = Math.floor((diff % 3600000) / 60000), s = Math.floor((diff % 60000) / 1000);
        container.innerHTML = `<div style="text-align:center;padding:16px 0;">
            <div style="font-size:16px;font-weight:bold;margin-bottom:12px;">${data.title || 'Countdown'}</div>
            <div style="display:flex;gap:12px;justify-content:center;">
                ${[{v:d,l:'days'},{v:h,l:'hrs'},{v:m,l:'min'},{v:s,l:'sec'}].map(x =>
                    `<div><div style="font-size:32px;font-weight:bold;color:${x.l==='sec'?'#ffd43b':'#667eea'};font-variant-numeric:tabular-nums;">${String(x.v).padStart(2,'0')}</div><div style="font-size:11px;color:#888;">${x.l}</div></div>`
                ).join('')}
            </div>
            <div style="color:#888;font-size:12px;margin-top:12px;">Target: ${target.toLocaleDateString([], {month:'long',day:'numeric',year:'numeric'})}</div>
        </div>`;
    }
    update();
    if (activeTimers[`cd-${widget.id}`]) clearInterval(activeTimers[`cd-${widget.id}`]);
    activeTimers[`cd-${widget.id}`] = setInterval(update, 1000);
}


// ─── YouTube Player Widget ────────────────────────────────────

function renderYouTube(container, widget) {
    const ytData = widget.adaptive_card?._youtube;

    // If no custom _youtube payload, fall back to AdaptiveCard (auth screens, errors)
    if (!ytData || !ytData.videos || !ytData.videos.length) {
        renderAdaptiveCard(widget.adaptive_card, container);
        return;
    }

    const videos = ytData.videos;
    const query = ytData.query || '';
    const wid = widget.id;
    let currentIdx = 0;

    function render(idx) {
        currentIdx = idx;
        const v = videos[idx];
        let html = `<div class="yt-widget">`;

        // Header
        html += `<div class="yt-header">
            <span class="yt-logo">▶</span>
            <span class="yt-title-text">${query ? escHtml(query) : 'YouTube'}</span>
        </div>`;

        // Player iframe
        html += `<div class="yt-player-wrap">
            <iframe
                id="yt-frame-${wid}"
                src="https://www.youtube.com/embed/${v.video_id}?autoplay=1&rel=0&modestbranding=1&color=white"
                frameborder="0"
                allow="autoplay; encrypted-media; picture-in-picture"
                allowfullscreen
            ></iframe>
        </div>`;

        // Now-playing info
        html += `<div class="yt-now-playing">
            <div class="yt-np-title">${escHtml(v.title)}</div>
            <div class="yt-np-channel">${escHtml(v.channel)}</div>
        </div>`;

        // Playlist
        if (videos.length > 1) {
            html += `<div class="yt-playlist">`;
            videos.forEach((item, i) => {
                const active = i === idx ? 'yt-pl-active' : '';
                html += `<div class="yt-pl-item ${active}" onclick="ytPlayAt('${wid}', ${i})">
                    <div class="yt-pl-idx">${i === idx ? '♫' : i + 1}</div>
                    <img class="yt-pl-thumb" src="${item.thumbnail}" alt="" loading="lazy">
                    <div class="yt-pl-info">
                        <div class="yt-pl-title">${escHtml(item.title)}</div>
                        <div class="yt-pl-ch">${escHtml(item.channel)}</div>
                    </div>
                </div>`;
            });
            html += `</div>`;
        }

        html += `</div>`;
        container.innerHTML = html;
    }

    // Store render function so playlist clicks work
    window._ytRenders = window._ytRenders || {};
    window._ytRenders[wid] = render;

    render(0);
}

function ytPlayAt(wid, idx) {
    if (window._ytRenders && window._ytRenders[wid]) {
        window._ytRenders[wid](idx);
    }
}

function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}


// ─── Credential Setup Widget ─────────────────────────────────

function renderCredentialSetup(container, widget) {
    const setup = widget.adaptive_card._credential_setup;
    const fields = setup.fields || [];
    const wid = widget.id;
    const ds = setup.data_source;

    // First render the adaptive card body (instructions)
    const cardBody = widget.adaptive_card;
    let html = `<div class="cred-setup">`;

    // Render the instructions from the adaptive card
    if (cardBody.body) {
        cardBody.body.forEach(el => {
            if (el.type === 'TextBlock') {
                const txt = (el.text || '').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
                const size = {'Large':'20px','Medium':'16px','Small':'13px'}[el.size] || '14px';
                const weight = el.weight === 'Bolder' ? 'bold' : 'normal';
                const color = el.isSubtle ? '#888' : '#e0e0e0';
                html += `<p style="font-size:${size};font-weight:${weight};color:${color};margin:4px 0;">${txt}</p>`;
            } else if (el.type === 'ActionSet' && el.actions) {
                el.actions.forEach(a => {
                    if (a.type === 'Action.OpenUrl') {
                        html += `<a href="${a.url}" target="_blank" class="action-btn primary" style="display:inline-block;margin:6px 0;text-decoration:none;font-size:12px;">${a.title}</a>`;
                    }
                });
            }
        });
    }

    // Credential input form
    html += `<div class="cred-form" id="cred-form-${wid}">`;
    fields.forEach(f => {
        const val = f.default || '';
        html += `<div class="cred-field">`;
        html += `<label class="cred-label">${escHtml(f.label)}</label>`;
        html += `<input type="text" class="cred-input" id="cred-${wid}-${f.key}" 
            placeholder="${escHtml(f.placeholder)}" value="${escHtml(val)}" 
            data-key="${f.key}" autocomplete="off" spellcheck="false">`;
        html += `</div>`;
    });
    html += `<div class="cred-actions">`;
    html += `<button class="action-btn primary" onclick="submitCredentials('${wid}', '${ds}')">Save & Activate</button>`;
    html += `<span id="cred-status-${wid}" class="cred-status"></span>`;
    html += `</div></div></div>`;

    container.innerHTML = html;
}

async function submitCredentials(wid, dataSource) {
    const form = document.getElementById(`cred-form-${wid}`);
    const status = document.getElementById(`cred-status-${wid}`);
    if (!form || !status) return;

    const inputs = form.querySelectorAll('.cred-input');
    const credentials = {};
    let empty = false;

    inputs.forEach(inp => {
        const key = inp.dataset.key;
        const val = inp.value.trim();
        if (key && val) {
            credentials[key] = val;
        } else if (key && !inp.placeholder.includes('optional')) {
            empty = true;
            inp.style.borderColor = '#ff6b6b';
        }
    });

    if (empty) {
        status.textContent = '⚠️ Please fill all required fields';
        status.style.color = '#ff6b6b';
        return;
    }

    status.textContent = '💾 Saving...';
    status.style.color = '#667eea';

    try {
        const r = await fetch(`${API_BASE}/credentials`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data_source: dataSource, credentials }),
        });

        if (!r.ok) {
            const err = await r.json();
            throw new Error(err.detail || 'Save failed');
        }

        const result = await r.json();
        status.textContent = '✅ Saved! Refreshing widget...';
        status.style.color = '#51cf66';

        // Re-forge the widget with the same prompt
        const widgetEl = document.getElementById(`widget-${wid}`);
        const prompt = widgetEl?.querySelector('.widget-prompt')?.textContent?.replace(/^"|"$/g, '').split('⚡')[0].trim();

        if (prompt) {
            // Delete old widget and re-forge
            setTimeout(async () => {
                await deleteWidget(wid);
                document.getElementById('prompt-input').value = prompt;
                await forgeWidget();
            }, 800);
        }
    } catch (e) {
        status.textContent = `❌ ${e.message}`;
        status.style.color = '#ff6b6b';
    }
}


// ─── Clipboard History Widget ─────────────────────────────────

function renderClipboard(container, widget) {
    const clipData = widget.adaptive_card?._clipboard;

    if (!clipData || !clipData.items || !clipData.items.length) {
        container.innerHTML = `<div class="cb-widget">
            <div class="cb-header"><span class="cb-icon">📋</span><span class="cb-title">Clipboard History</span></div>
            <div style="text-align:center;padding:20px;color:#888;">No clipboard items yet.<br>Copy something to start tracking!</div>
        </div>`;
        return;
    }

    const items = clipData.items;
    const wid = widget.id;

    const typeIcons = { url: '🔗', email: '✉️', phone: '📞', code: '💻', long_text: '📄', text: '📝' };

    let html = `<div class="cb-widget">`;
    html += `<div class="cb-header"><span class="cb-icon">📋</span><span class="cb-title">Clipboard History</span><span class="cb-count">${items.length} items</span></div>`;
    html += `<div class="cb-list">`;

    items.forEach((item, i) => {
        const icon = typeIcons[item.content_type] || '📝';
        const pinClass = item.pinned ? 'cb-pinned' : '';
        const text = escHtml(item.text || '').substring(0, 120);
        const time = item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';

        html += `<div class="cb-item ${pinClass}" onclick="cbCopy('${wid}', ${i})" title="Click to copy">`;
        html += `<div class="cb-item-icon">${icon}</div>`;
        html += `<div class="cb-item-body">`;
        html += `<div class="cb-item-text">${text}</div>`;
        html += `<div class="cb-item-meta"><span class="cb-type">${item.content_type}</span><span>${time}</span></div>`;
        html += `</div>`;
        html += `<div class="cb-item-pin">${item.pinned ? '📌' : ''}</div>`;
        html += `</div>`;
    });

    html += `</div></div>`;
    container.innerHTML = html;
}

function cbCopy(wid, idx) {
    // Get the widget data to find the text
    const container = document.getElementById(`body-${wid}`);
    if (!container) return;
    const items = container.querySelectorAll('.cb-item');
    const item = items[idx];
    if (!item) return;
    const text = item.querySelector('.cb-item-text')?.textContent || '';
    navigator.clipboard.writeText(text).then(() => {
        item.style.background = 'rgba(102, 126, 234, 0.2)';
        setTimeout(() => item.style.background = '', 500);
    });
}


// ─── Adaptive Card Renderer (non-interactive widgets) ─────────

function renderAdaptiveCard(cardJson, container) {
    if (typeof container === 'string') container = document.getElementById(container);
    if (!container) return;

    if (typeof AdaptiveCards !== 'undefined') {
        try {
            // Enable markdown processing (bold / italic)
            AdaptiveCards.AdaptiveCard.onProcessMarkdown = function(text, result) {
                result.outputHtml = text
                    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\*(.+?)\*/g, '<em>$1</em>')
                    .replace(/\n/g, '<br>');
                result.didProcess = true;
            };

            const ac = new AdaptiveCards.AdaptiveCard();
            ac.hostConfig = new AdaptiveCards.HostConfig({
                fontFamily: "'Segoe UI', system-ui, sans-serif",
                containerStyles: {
                    default: { backgroundColor: "#00000000", foregroundColors: {
                        default: { default: "#e0e0e0", subtle: "#888888" },
                        accent: { default: "#667eea", subtle: "#667eea" },
                        attention: { default: "#ff6b6b", subtle: "#ff6b6b" },
                        good: { default: "#51cf66", subtle: "#51cf66" },
                        warning: { default: "#ffd43b", subtle: "#ffd43b" },
                    }},
                    emphasis: { backgroundColor: "#1a1a2e", foregroundColors: {
                        default: { default: "#e0e0e0", subtle: "#888888" },
                        accent: { default: "#667eea", subtle: "#667eea" },
                        attention: { default: "#ff6b6b", subtle: "#ff6b6b" },
                        good: { default: "#51cf66", subtle: "#51cf66" },
                        warning: { default: "#ffd43b", subtle: "#ffd43b" },
                    }}
                }
            });
            ac.onExecuteAction = (a) => { if (a instanceof AdaptiveCards.OpenUrlAction) window.open(a.url, '_blank'); };
            ac.parse(cardJson);
            container.innerHTML = '';
            container.appendChild(ac.render());
            return;
        } catch (e) { console.error('AC error:', e); }
    }
    container.innerHTML = renderCardAsHTML(cardJson);
}

function renderCardAsHTML(cj) {
    if (!cj?.body) return '<p style="color:#888;">No card data</p>';
    let h = '<div class="fallback-card">';
    cj.body.forEach(el => h += renderElement(el));
    if (cj.actions) {
        h += '<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;">';
        cj.actions.forEach(a => {
            if (a.type === 'Action.OpenUrl') h += `<a href="${a.url}" target="_blank" class="action-btn primary" style="text-decoration:none;">${a.title}</a>`;
            else h += `<button class="action-btn">${a.title}</button>`;
        });
        h += '</div>';
    }
    return h + '</div>';
}

function renderElement(el) {
    if (!el?.type) return '';
    const C = { Good:'#51cf66', Attention:'#ff6b6b', Warning:'#ffd43b', Accent:'#667eea' };
    const S = { Small:'12px', Default:'14px', Medium:'16px', Large:'20px', ExtraLarge:'28px' };
    switch (el.type) {
        case 'TextBlock': {
            let txt = (el.text||'').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.+?)\*/g, '<em>$1</em>');
            const clickable = el.selectAction?.type === 'Action.OpenUrl' ? `cursor:pointer;text-decoration:underline;` : '';
            const onclick = el.selectAction?.url ? ` onclick="window.open('${el.selectAction.url}','_blank')"` : '';
            return `<p style="font-size:${S[el.size]||'14px'};color:${C[el.color]||(el.isSubtle?'#888':'#e0e0e0')};font-weight:${el.weight==='Bolder'?'bold':'normal'};text-align:${el.horizontalAlignment||'left'};margin:4px 0;${clickable}"${onclick}>${txt}</p>`;
        }
        case 'Image': return `<img src="${el.url}" alt="${el.altText||''}" style="max-width:100%;border-radius:8px;margin:8px 0;">`;
        case 'Container': { const bg = el.style==='emphasis'?'background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:8px 12px;':''; const cClick = el.selectAction?.url ? ` onclick="window.open('${el.selectAction.url}','_blank')" style="cursor:pointer;margin:6px 0;${bg}${el.separator?'padding-top:8px;border-top:1px solid #333;':''}"` : ` style="margin:6px 0;${bg}${el.separator?'padding-top:8px;border-top:1px solid #333;':''}"`; let h = `<div${cClick}>`; (el.items||[]).forEach(i=>h+=renderElement(i)); return h+'</div>'; }
        case 'ColumnSet': { let h='<div style="display:flex;gap:16px;margin:8px 0;">'; (el.columns||[]).forEach(c=>{ h+=`<div style="flex:${c.width==='auto'?'0 0 auto':'1'};text-align:center;">`; (c.items||[]).forEach(i=>h+=renderElement(i)); h+='</div>'; }); return h+'</div>'; }
        case 'FactSet': { let h=`<div style="margin:8px 0;${el.separator?'padding-top:8px;border-top:1px solid #333;':''}">`; (el.facts||[]).forEach(f=>h+=`<div style="display:flex;gap:12px;padding:3px 0;"><span style="color:#888;min-width:80px;">${f.title}</span><span style="color:#e0e0e0;font-weight:bold;">${f.value}</span></div>`); return h+'</div>'; }
        default: return '';
    }
}


// ─── Standard Actions ─────────────────────────────────────────

async function refreshWidget(wid) {
    // Manual refresh — still respects the mutation lock
    if (_refreshState.mutating) return;
    if (_refreshState.inflight.has(wid)) return;
    _refreshState.inflight.add(wid);
    try {
        const r = await fetch(`${API_BASE}/refresh`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({widget_id:wid}) });
        if (r.ok) renderWidget(await r.json());
    } catch (e) { console.error('Refresh failed:', e); }
    finally { _refreshState.inflight.delete(wid); }
}

async function deleteWidget(wid) {
    _refreshState.mutating = true;          // ━ lock
    _stopAutoRefresh(wid);
    Object.keys(activeTimers).forEach(k => { if (k.includes(wid)) { clearInterval(activeTimers[k]); delete activeTimers[k]; } });
    const sid = wid.replace(/-/g, '_');
    delete window[`_timerToggle_${sid}`];
    delete window[`_timerReset_${sid}`];
    document.getElementById(`widget-${wid}`)?.remove();
    try { await fetch(`${API_BASE}/${wid}`, { method: 'DELETE' }); } catch(e) {}
    _refreshState.mutating = false;         // ━ unlock
}

// ─── Widget Menu & Size Control ───────────────────────────────

function toggleWidgetMenu(event, wid) {
    event.stopPropagation();
    // Close all other menus first
    document.querySelectorAll('.widget-menu.open').forEach(m => {
        if (m.id !== `menu-${wid}`) m.classList.remove('open');
    });
    const menu = document.getElementById(`menu-${wid}`);
    if (menu) menu.classList.toggle('open');
}

function setWidgetSize(wid, size) {
    const card = document.getElementById(`widget-${wid}`);
    if (!card) return;
    card.classList.remove('widget-sm', 'widget-md', 'widget-lg');
    card.classList.add(`widget-${size}`);
    // Update active state in menu buttons
    const menu = document.getElementById(`menu-${wid}`);
    if (menu) {
        menu.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        const labels = {'sm': 'Small', 'md': 'Medium', 'lg': 'Large'};
        menu.querySelectorAll('button').forEach(b => {
            if (b.textContent === labels[size]) b.classList.add('active');
        });
        menu.classList.remove('open');
    }
}

async function reconfigureWidget(wid) {
    // Close the menu
    document.querySelectorAll('.widget-menu.open').forEach(m => m.classList.remove('open'));

    if (!confirm('This will reset the API credentials for this widget type. You will need to re-enter them. Continue?')) return;

    try {
        const r = await fetch(`${API_BASE}/reconfigure`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ widget_id: wid }),
        });
        if (!r.ok) {
            const err = await r.json();
            alert(err.detail || 'Reconfigure failed');
            return;
        }
        const widget = await r.json();
        // Re-render the widget as a credential setup card
        renderWidget(widget);
    } catch (e) {
        alert('Failed to reconfigure: ' + e.message);
    }
}

async function toggleWidget(wid, currentlyDisabled) {
    // Close the menu
    document.querySelectorAll('.widget-menu.open').forEach(m => m.classList.remove('open'));

    const enabling = currentlyDisabled;
    try {
        const r = await fetch(`${API_BASE}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ widget_id: wid, enabled: enabling }),
        });
        if (!r.ok) {
            const err = await r.json();
            alert(err.detail || 'Toggle failed');
            return;
        }
        const widget = await r.json();
        // Re-render and restart/stop auto-refresh
        const card = document.getElementById(`widget-${wid}`);
        if (card) card.remove();
        addWidgetToBoard(widget);
        if (!enabling) _stopAutoRefresh(wid);
    } catch (e) {
        alert('Failed to toggle widget: ' + e.message);
    }
}

// Close menus when clicking outside
document.addEventListener('click', () => {
    document.querySelectorAll('.widget-menu.open').forEach(m => m.classList.remove('open'));
});

async function loadWidgets() {
    try {
        const r = await fetch(`${API_BASE}/list`);
        (await r.json()).forEach(addWidgetToBoard);
    } catch (e) { console.log('No existing widgets'); }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('prompt-input').addEventListener('keydown', e => { if (e.key === 'Enter') forgeWidget(); });
    loadWidgets();
    loadSuggestions();
    // Escape key closes suggestions popup
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') document.getElementById('suggestions-overlay')?.classList.remove('open');
    });
});


// ─── Widget Suggestions ───────────────────────────────────────

const CATEGORY_ICONS = {
    Essentials: '⚡', Dev: '🛠', Work: '📋', Music: '🎵', Media: '🎬',
    Web: '🌐', Gaming: '🎮', Creative: '🎨', Sports: '🏏', Finance: '📈',
    Utility: '🔧', Fun: '🎉'
};

async function loadSuggestions() {
    try {
        const r = await fetch(`${API_BASE}/suggestions`);
        const data = await r.json();
        const items = data.suggestions || [];
        if (!items.length) return;

        // Store suggestions data for popup
        window._sugData = { items, appCount: data.app_count || 0 };

        // Group by category
        const groups = {};
        items.forEach(s => {
            const cat = s.category || 'Other';
            if (!groups[cat]) groups[cat] = [];
            groups[cat].push(s);
        });

        let html = '';
        for (const [cat, chips] of Object.entries(groups)) {
            const icon = CATEGORY_ICONS[cat] || '✦';
            html += `<div class="sug-group">`;
            html += `<div class="sug-group-label">${icon} ${cat}</div>`;
            html += `<div class="sug-group-grid">`;
            chips.forEach(s => {
                const p = s.prompt.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                const color = s.color || '#667eea';
                html += `<button class="sug-chip" style="--chip-accent:${color}" onclick="useSuggestion('${p}')" title="${s.desc}">`;
                html += `<span class="sug-chip-icon">${icon}</span>`;
                html += `<span class="sug-chip-text">`;
                html += `<span class="sug-chip-title">${s.title}</span>`;
                html += `<span class="sug-chip-desc">${s.desc}</span>`;
                html += `</span></button>`;
            });
            html += `</div></div>`;
        }

        document.getElementById('sug-popup-body').innerHTML = html;
        document.getElementById('sug-popup-count').textContent = `${items.length} widgets · ${data.app_count || 0} apps detected`;
    } catch (e) { /* ignore */ }
}

function toggleSuggestions() {
    const overlay = document.getElementById('suggestions-overlay');
    overlay.classList.toggle('open');
}

function closeSuggestionsOverlay(e) {
    if (e.target.id === 'suggestions-overlay') {
        e.target.classList.remove('open');
    }
}

function useSuggestion(prompt) {
    if (prompt === '__auth_google__') {
        window.location.href = '/auth/google';
        return;
    }
    // Close popup
    document.getElementById('suggestions-overlay')?.classList.remove('open');
    document.getElementById('prompt-input').value = prompt;
    forgeWidget();
}
