using System;
using System.Threading;
using Microsoft.Windows.Widgets;
using WidgetForgeProvider.Widgets;

namespace WidgetForgeProvider;

/// <summary>
/// Widget Forge Provider - bridges the Python backend to Windows 11 Widgets Board.
/// 
/// Architecture:
///   User prompts → Python Backend (FastAPI) → Adaptive Card JSON
///   This app → Reads from backend API → Serves cards to Windows Widgets Board
///   
/// The Python backend runs separately (uvicorn) and this app calls its API
/// to get widget configurations and adaptive card templates.
/// </summary>
class Program
{
    static ManualResetEvent _quitEvent = new ManualResetEvent(false);

    static void Main(string[] args)
    {
        Console.WriteLine("╔══════════════════════════════════════════╗");
        Console.WriteLine("║     Widget Forge - Windows Provider     ║");
        Console.WriteLine("║  Bridging AI Widgets → Windows Desktop  ║");
        Console.WriteLine("╚══════════════════════════════════════════╝");
        Console.WriteLine();

        // Register the widget provider with Windows
        try
        {
            WidgetProvider.AddWidgetProvider<WidgetForgeWidgetProvider>(
                "WidgetForgeProvider");

            Console.WriteLine("[OK] Widget provider registered with Windows");
            Console.WriteLine("[..] Waiting for widget events...");
            Console.WriteLine("[..] Backend API: http://localhost:8000");
            Console.WriteLine();
            Console.WriteLine("Press Ctrl+C to exit.");

            Console.CancelKeyPress += (sender, e) =>
            {
                e.Cancel = true;
                _quitEvent.Set();
            };

            // Keep the process alive to service widget requests
            _quitEvent.WaitOne();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ERROR] Failed to register widget provider: {ex.Message}");
            Console.WriteLine();
            Console.WriteLine("Make sure:");
            Console.WriteLine("  1. You're running Windows 11 22H2+");
            Console.WriteLine("  2. Windows App SDK is installed");
            Console.WriteLine("  3. The app is registered in the manifest");
        }
    }
}
