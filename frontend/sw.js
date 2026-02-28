// Service Worker for Widget Forge - PWA Widget Provider
// Handles widget lifecycle events from the Windows 11 Widgets Board

const API_BASE = self.location.origin + '/api/widgets';

// Widget tag → prompt mapping
const WIDGET_PROMPTS = {
    'widget-system-health': 'Show system health',
    'widget-github-activity': 'Show my GitHub activity',
    'widget-hacker-news': 'Show Hacker News',
    'widget-standup-prep': 'What did I work on yesterday',
};

// ─── Standard PWA lifecycle ───────────────────────────────────

self.addEventListener('install', (event) => {
    console.log('[SW] Installing Widget Forge service worker');
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('[SW] Activating Widget Forge service worker');
    event.waitUntil(clients.claim());
});

// ─── Widget lifecycle events ──────────────────────────────────

// Called when user pins a widget from the Widget Picker
self.addEventListener('widgetinstall', (event) => {
    console.log('[SW] Widget installed:', event.widget.definition.tag);
    event.waitUntil(updateWidget(event.widget));
});

// Called when widget becomes visible (board opened)
self.addEventListener('widgetresume', (event) => {
    console.log('[SW] Widget resumed:', event.widget.definition.tag);
    event.waitUntil(updateWidget(event.widget));
});

// Called when user clicks an action button on the widget
self.addEventListener('widgetclick', (event) => {
    const action = event.action;
    const tag = event.widget.definition.tag;
    console.log(`[SW] Widget click: ${action} on ${tag}`);

    if (action === 'refresh') {
        event.waitUntil(updateWidget(event.widget));
    } else if (action === 'open-app') {
        event.waitUntil(clients.openWindow('/'));
    }
});

// Called when user removes the widget
self.addEventListener('widgetuninstall', (event) => {
    console.log('[SW] Widget uninstalled:', event.widget.definition.tag);
});

// ─── Widget update logic ──────────────────────────────────────

async function updateWidget(widget) {
    const tag = widget.definition.tag;
    const prompt = WIDGET_PROMPTS[tag] || 'Show system health';

    try {
        console.log(`[SW] Fetching data for "${prompt}"...`);

        // Call our backend to forge the widget
        const response = await fetch(`${API_BASE}/forge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt }),
        });

        if (!response.ok) throw new Error(`API returned ${response.status}`);

        const result = await response.json();

        // Push the adaptive card to the Windows Widgets Board
        await self.widgets.updateByTag(tag, {
            template: JSON.stringify(result.adaptive_card),
            data: JSON.stringify(result.data),
        });

        console.log(`[SW] Widget "${tag}" updated (${result.timing?.total_ms}ms)`);
    } catch (error) {
        console.error(`[SW] Failed to update widget "${tag}":`, error);

        // Show error state
        const errorTemplate = {
            type: 'AdaptiveCard',
            version: '1.6',
            $schema: 'http://adaptivecards.io/schemas/adaptive-card.json',
            body: [
                { type: 'TextBlock', text: 'Widget Forge', size: 'Medium', weight: 'Bolder', wrap: true },
                { type: 'TextBlock', text: 'Unable to fetch data. Is the backend running?', wrap: true, isSubtle: true },
            ],
            actions: [
                { type: 'Action.Execute', title: 'Retry', verb: 'refresh' },
                { type: 'Action.Execute', title: 'Open App', verb: 'open-app' },
            ],
        };

        try {
            await self.widgets.updateByTag(tag, {
                template: JSON.stringify(errorTemplate),
                data: '{}',
            });
        } catch (e) { /* ignore */ }
    }
}

// ─── Periodic background updates ──────────────────────────────

self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'widget-update') {
        event.waitUntil(updateAllWidgets());
    }
});

async function updateAllWidgets() {
    if (!self.widgets) return;
    try {
        const widgetList = await self.widgets.getByHostTag('*');
        for (const widget of widgetList) {
            await updateWidget(widget);
        }
    } catch (error) {
        console.error('[SW] Failed to update all widgets:', error);
    }
}
