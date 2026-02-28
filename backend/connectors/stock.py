"""
Stock price connector using free Yahoo Finance API (no key needed).
"""
import httpx
from datetime import datetime, timezone


async def get_stock_price(symbol: str) -> dict:
    """
    Fetch current stock price for a given symbol.
    Uses Yahoo Finance's public query endpoint (free, no API key).
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL, ADBE, MSFT)
    
    Returns:
        dict with price, change, and other stock info
    """
    symbol = symbol.upper().strip()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params={
                "interval": "1d",
                "range": "5d",
            }, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            data = response.json()
        
        result = data.get("chart", {}).get("result", [])
        if not result:
            return {
                "symbol": symbol,
                "error": f"No data found for {symbol}",
                "found": False,
            }
        
        meta = result[0].get("meta", {})
        indicators = result[0].get("indicators", {})
        quotes = indicators.get("quote", [{}])[0]
        
        # Get latest close prices
        closes = quotes.get("close", [])
        closes = [c for c in closes if c is not None]
        
        current_price = meta.get("regularMarketPrice", closes[-1] if closes else 0)
        prev_close = meta.get("previousClose", closes[-2] if len(closes) >= 2 else current_price)
        
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        return {
            "symbol": symbol,
            "found": True,
            "name": meta.get("shortName", meta.get("symbol", symbol)),
            "price": round(current_price, 2),
            "previous_close": round(prev_close, 2),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "currency": meta.get("currency", "USD"),
            "exchange": meta.get("exchangeName", ""),
            "market_state": meta.get("marketState", "CLOSED"),
            "day_high": meta.get("regularMarketDayHigh", round(max(quotes.get("high", [0]) or [0]), 2)),
            "day_low": meta.get("regularMarketDayLow", round(min([x for x in (quotes.get("low", [0]) or [0]) if x] or [0]), 2)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except httpx.HTTPStatusError as e:
        return {
            "symbol": symbol,
            "found": False,
            "error": f"API error: {e.response.status_code}",
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "found": False,
            "error": str(e),
        }
