using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;
using Microsoft.Windows.Widgets.Providers;

namespace WidgetForgeProvider.Widgets;

/// <summary>
/// Implements IWidgetProvider to bridge Widget Forge backend → Windows 11 Widgets Board.
/// 
/// This provider:
///   1. Receives widget lifecycle events from Windows
///   2. Calls the Widget Forge Python API to get adaptive cards
///   3. Sends the cards back to the Widgets Board for rendering
/// </summary>
public class WidgetForgeWidgetProvider : IWidgetProvider
{
    private static readonly HttpClient _httpClient = new()
    {
        BaseAddress = new Uri("http://localhost:8000"),
        Timeout = TimeSpan.FromSeconds(30)
    };

    // Track active widgets: widgetId → widget info
    private readonly Dictionary<string, WidgetInfo> _activeWidgets = new();

    // Default widget templates for each type
    private static readonly Dictionary<string, string> _defaultPrompts = new()
    {
        { "SystemHealth", "Show system health" },
        { "GitHubActivity", "Show my GitHub activity" },
        { "HackerNews", "Show Hacker News" },
        { "Standup", "What did I work on yesterday" },
    };

    /// <summary>
    /// Called when a user pins the widget from the widget picker.
    /// </summary>
    public void CreateWidget(WidgetContext widgetContext)
    {
        string widgetId = widgetContext.Id;
        string widgetName = widgetContext.DefinitionId;

        Console.WriteLine($"[+] Widget created: {widgetName} (id: {widgetId})");

        var info = new WidgetInfo
        {
            WidgetId = widgetId,
            WidgetName = widgetName,
            Prompt = _defaultPrompts.GetValueOrDefault(widgetName, "Show system health"),
            IsActive = true
        };

        _activeWidgets[widgetId] = info;

        // Fetch and update the widget with data from our backend
        _ = UpdateWidgetAsync(widgetId);
    }

    /// <summary>
    /// Called when a user removes the widget from the board.
    /// </summary>
    public void DeleteWidget(string widgetId, string customState)
    {
        Console.WriteLine($"[-] Widget deleted: {widgetId}");
        _activeWidgets.Remove(widgetId);
    }

    /// <summary>
    /// Called when the user clicks a button/action on the widget.
    /// </summary>
    public void OnActionInvoked(WidgetActionInvokedArgs actionInvokedArgs)
    {
        string widgetId = actionInvokedArgs.WidgetContext.Id;
        string action = actionInvokedArgs.Verb;

        Console.WriteLine($"[>] Action: {action} on widget {widgetId}");

        switch (action)
        {
            case "refresh":
                _ = UpdateWidgetAsync(widgetId);
                break;
            case "configure":
                // Could open a configuration dialog
                break;
            default:
                Console.WriteLine($"    Unknown action: {action}");
                break;
        }
    }

    /// <summary>
    /// Called when the widget size is changed by the user.
    /// </summary>
    public void OnWidgetContextChanged(WidgetContextChangedArgs contextChangedArgs)
    {
        string widgetId = contextChangedArgs.WidgetContext.Id;
        var size = contextChangedArgs.WidgetContext.Size;

        Console.WriteLine($"[~] Widget context changed: {widgetId}, size={size}");

        if (_activeWidgets.TryGetValue(widgetId, out var info))
        {
            info.Size = size.ToString();
            _ = UpdateWidgetAsync(widgetId);
        }
    }

    /// <summary>
    /// Called when the Widgets Board is visible and interested in updates.
    /// </summary>
    public void Activate(WidgetContext widgetContext)
    {
        string widgetId = widgetContext.Id;
        Console.WriteLine($"[*] Widget activated: {widgetId}");

        if (_activeWidgets.TryGetValue(widgetId, out var info))
        {
            info.IsActive = true;
            _ = UpdateWidgetAsync(widgetId);
        }
    }

    /// <summary>
    /// Called when the Widgets Board is hidden / no longer needs updates.
    /// </summary>
    public void Deactivate(string widgetId)
    {
        Console.WriteLine($"[.] Widget deactivated: {widgetId}");

        if (_activeWidgets.TryGetValue(widgetId, out var info))
        {
            info.IsActive = false;
        }
    }

    /// <summary>
    /// Core method: calls Widget Forge API and pushes the adaptive card to Windows.
    /// </summary>
    private async Task UpdateWidgetAsync(string widgetId)
    {
        if (!_activeWidgets.TryGetValue(widgetId, out var info))
            return;

        try
        {
            Console.WriteLine($"    Fetching widget data for: \"{info.Prompt}\"");

            // Call our Python backend to forge the widget
            var request = new { prompt = info.Prompt };
            var jsonContent = new StringContent(
                JsonSerializer.Serialize(request),
                System.Text.Encoding.UTF8,
                "application/json");

            var response = await _httpClient.PostAsync("/api/widgets/forge", jsonContent);
            response.EnsureSuccessStatusCode();

            var responseJson = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(responseJson);
            var root = doc.RootElement;

            // Extract the adaptive card and data from the response
            var adaptiveCard = root.GetProperty("adaptive_card").GetRawText();
            var widgetData = root.GetProperty("data").GetRawText();

            // Build the update options
            var updateOptions = new WidgetUpdateRequestOptions(widgetId)
            {
                Template = adaptiveCard,
                Data = widgetData,
                CustomState = JsonSerializer.Serialize(new
                {
                    prompt = info.Prompt,
                    forgeId = root.GetProperty("id").GetString(),
                    lastUpdated = DateTime.UtcNow.ToString("o")
                })
            };

            // Push the update to the Windows Widgets Board
            WidgetManager.GetDefault().UpdateWidget(updateOptions);

            var timing = root.GetProperty("timing");
            var totalMs = timing.GetProperty("total_ms").GetInt32();
            Console.WriteLine($"    [OK] Widget updated in {totalMs}ms");
        }
        catch (HttpRequestException ex)
        {
            Console.WriteLine($"    [!] Backend not reachable: {ex.Message}");
            Console.WriteLine($"    [!] Make sure 'uvicorn backend.main:app --port 8000' is running");

            // Show error card
            var errorCard = GetErrorCard("Backend not running",
                "Start the Widget Forge backend:\nuvicorn backend.main:app --port 8000");
            var updateOptions = new WidgetUpdateRequestOptions(widgetId)
            {
                Template = errorCard
            };
            WidgetManager.GetDefault().UpdateWidget(updateOptions);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"    [!] Update failed: {ex.Message}");
        }
    }

    /// <summary>
    /// Generate an error card when the backend is unreachable.
    /// </summary>
    private static string GetErrorCard(string title, string message)
    {
        var card = new
        {
            type = "AdaptiveCard",
            version = "1.6",
            body = new object[]
            {
                new { type = "TextBlock", text = "Widget Forge", size = "Medium", weight = "Bolder", wrap = true },
                new { type = "TextBlock", text = title, color = "Attention", weight = "Bolder", wrap = true },
                new { type = "TextBlock", text = message, wrap = true, size = "Small" }
            },
            actions = new object[]
            {
                new { type = "Action.Execute", title = "Retry", verb = "refresh" }
            },
            schema = "http://adaptivecards.io/schemas/adaptive-card.json"
        };
        return JsonSerializer.Serialize(card);
    }
}

/// <summary>
/// Tracks state for each active widget instance.
/// </summary>
internal class WidgetInfo
{
    public string WidgetId { get; set; } = "";
    public string WidgetName { get; set; } = "";
    public string Prompt { get; set; } = "";
    public bool IsActive { get; set; }
    public string Size { get; set; } = "Medium";
}
