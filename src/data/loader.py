"""
EvoAlpha — Data Loader
Loads data from Supabase or generates mock data for development.

Supabase tables:
  equity_bars    — 50 US stocks, 1yr daily OHLCV
  crypto_bars    — 73 crypto pairs, daily OHLCV
  fx_bars        — 10 FX pairs, 1yr daily OHLCV
  trends_interest — 1000 Google Trends keywords, 5yr weekly
  trends_keywords — keyword metadata (category, source)
"""
import pandas as pd
import numpy as np
from config.settings import USE_MOCK_DATA

# Max rows per Supabase REST query (PostgREST default)
_PAGE_SIZE = 1000


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def load_data(
    target_symbol: str = "AAPL",
    target_asset_class: str = "equity",
    feature_symbols: list[str] | None = None,
    trend_keywords: list[str] | None = None,
) -> pd.DataFrame:
    """
    Build a merged daily DataFrame: target close price + feature columns.

    Args:
        target_symbol: the asset to predict (e.g. 'AAPL', 'BTC/USD', 'EURUSD')
        target_asset_class: 'equity', 'crypto', or 'fx'
        feature_symbols: other asset symbols to include as features
        trend_keywords: Google Trends keywords to include as features

    Returns:
        pd.DataFrame indexed by date, columns = [target, feature_1, feature_2, ...]
    """
    if USE_MOCK_DATA:
        return _generate_mock_data()

    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    if client is None:
        print("  ⚠ Supabase unavailable — falling back to mock data")
        return _generate_mock_data()

    # 1. Load target asset OHLCV
    target_col = f"{target_symbol}_close"
    target_df = _load_bars(client, target_symbol, target_asset_class)
    if target_df is None or target_df.empty:
        print(f"  ⚠ No data for target {target_symbol} — falling back to mock data")
        return _generate_mock_data()

    # Rename close → target column name
    target_df = target_df.rename(columns={"close": target_col})
    merged = target_df[[target_col]].copy()

    # Also add target OHLCV as extra features (open, high, low, volume)
    for col in ["open", "high", "low", "volume"]:
        if col in target_df.columns:
            merged[f"{target_symbol}_{col}"] = target_df[col]

    # 2. Load feature assets
    if feature_symbols:
        for sym in feature_symbols:
            ac = _guess_asset_class(sym)
            feat_df = _load_bars(client, sym, ac)
            if feat_df is not None and not feat_df.empty:
                merged[f"{sym}_close"] = feat_df["close"]
                if "volume" in feat_df.columns:
                    merged[f"{sym}_volume"] = feat_df["volume"]

    # 3. Load Google Trends features
    if trend_keywords:
        for kw in trend_keywords:
            trend_df = _load_trend(client, kw)
            if trend_df is not None and not trend_df.empty:
                col_name = f"trend_{kw.replace(' ', '_')}"
                merged[col_name] = trend_df["interest"]

    # 4. Forward-fill (trends are weekly → fills weekdays), drop rows with NaN
    merged = merged.sort_index().ffill().dropna()

    if merged.empty:
        print("  ⚠ Merged dataset is empty — falling back to mock data")
        return _generate_mock_data()

    return merged


def get_available_features(df: pd.DataFrame, target_col: str) -> list[str]:
    """Return list of available feature column names (everything except target)."""
    return [c for c in df.columns if c != target_col]


def list_available_assets() -> dict:
    """
    Query Supabase for all available asset symbols.
    Returns dict with keys 'equity', 'crypto', 'fx', each mapping to a list of dicts.
    """
    if USE_MOCK_DATA:
        return {"equity": [], "crypto": [], "fx": [], "trends": []}

    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    if client is None:
        return {"equity": [], "crypto": [], "fx": [], "trends": []}

    result = {}
    for ac, table in [("equity", "equity_instruments"), ("crypto", "crypto_instruments"), ("fx", "fx_instruments")]:
        resp = client.table(table).select("symbol, name").execute()
        result[ac] = [{"symbol": r["symbol"], "name": r.get("name", "")} for r in resp.data]

    # Trends keywords
    resp = client.table("trends_keywords").select("keyword, category").execute()
    result["trends"] = [{"keyword": r["keyword"], "category": r.get("category", "")} for r in resp.data]

    return result


def search_trends_keywords(query: str) -> list[str]:
    """Search for matching trend keywords (case-insensitive substring match)."""
    if USE_MOCK_DATA:
        return []
    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    if client is None:
        return []
    resp = client.table("trends_keywords").select("keyword").ilike("keyword", f"%{query}%").limit(20).execute()
    return [r["keyword"] for r in resp.data]


# ─────────────────────────────────────────────
# Supabase helpers
# ─────────────────────────────────────────────

def _bars_table(asset_class: str) -> str:
    """Map asset class to Supabase table name."""
    return {"equity": "equity_bars", "crypto": "crypto_bars", "fx": "fx_bars"}[asset_class]


def _guess_asset_class(symbol: str) -> str:
    """Guess asset class from symbol format."""
    if "/" in symbol:
        return "crypto"
    elif len(symbol) == 6 and symbol.isalpha():
        return "fx"
    else:
        return "equity"


def _load_bars(client, symbol: str, asset_class: str) -> pd.DataFrame | None:
    """Load daily OHLCV bars for a single symbol from Supabase (handles pagination)."""
    table = _bars_table(asset_class)
    all_data = []
    offset = 0

    while True:
        resp = (
            client.table(table)
            .select("ts, open, high, low, close, volume")
            .eq("symbol", symbol)
            .eq("timeframe", "1Day")
            .order("ts")
            .range(offset, offset + _PAGE_SIZE - 1)
            .execute()
        )
        if not resp.data:
            break
        all_data.extend(resp.data)
        if len(resp.data) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE

    if not all_data:
        return None

    df = pd.DataFrame(all_data)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts").sort_index()
    # Normalize to date-only index (remove timezone)
    df.index = df.index.normalize().tz_localize(None)
    # Convert to float
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _load_trend(client, keyword: str) -> pd.DataFrame | None:
    """Load Google Trends interest over time for a keyword (handles pagination)."""
    all_data = []
    offset = 0

    while True:
        resp = (
            client.table("trends_interest")
            .select("ts, interest")
            .eq("keyword", keyword)
            .order("ts")
            .range(offset, offset + _PAGE_SIZE - 1)
            .execute()
        )
        if not resp.data:
            break
        all_data.extend(resp.data)
        if len(resp.data) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE

    if not all_data:
        return None

    df = pd.DataFrame(all_data)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts").sort_index()
    df.index = df.index.normalize().tz_localize(None)
    df["interest"] = pd.to_numeric(df["interest"], errors="coerce")
    return df


# ─────────────────────────────────────────────
# Mock data (for development / offline use)
# ─────────────────────────────────────────────

def _generate_mock_data(days: int = 1000) -> pd.DataFrame:
    """
    Generate realistic mock data for development/testing.
    Simulates: temperature, humidity, oil_price, gas_price,
    shipping_index, search_trend, air_quality, grid_demand.
    """
    np.random.seed(42)
    dates = pd.date_range(start="2020-01-01", periods=days, freq="D")

    # --- Temperature (seasonal + noise) ---
    day_of_year = np.arange(days) % 365
    temperature = 15 + 10 * np.sin(2 * np.pi * day_of_year / 365) + np.random.normal(0, 2, days)

    # --- Humidity (inversely correlated with temp + noise) ---
    humidity = 60 - 0.3 * temperature + np.random.normal(0, 5, days)

    # --- Oil price (random walk with slight drift + weak temp correlation) ---
    oil_returns = 0.0002 + 0.015 * np.random.randn(days)
    temp_anomaly = (temperature - temperature.mean()) / temperature.std()
    for i in range(3, days):
        oil_returns[i] += 0.002 * temp_anomaly[i - 3]  # hidden signal!
    oil_price = 60 * np.exp(np.cumsum(oil_returns))

    # --- Gas price (correlated with oil) ---
    gas_returns = 0.6 * oil_returns + 0.4 * 0.012 * np.random.randn(days)
    gas_price = 3.0 * np.exp(np.cumsum(gas_returns))

    # --- Shipping index (lagged oil correlation + seasonal) ---
    shipping_base = 1000 + 200 * np.sin(2 * np.pi * day_of_year / 365)
    shipping_index = shipping_base + np.random.normal(0, 50, days)
    for i in range(5, days):
        shipping_index[i] += 0.3 * (oil_price[i - 5] - oil_price[i - 6])

    # --- Search trend (random with occasional spikes) ---
    search_trend = np.abs(50 + 10 * np.random.randn(days))
    spike_days = np.random.choice(days, size=20, replace=False)
    search_trend[spike_days] *= 3

    # --- Air quality index ---
    air_quality = 40 + 15 * np.sin(2 * np.pi * day_of_year / 365 + np.pi) + np.random.normal(0, 8, days)

    # --- Grid demand ---
    day_of_week = np.arange(days) % 7
    grid_demand = 30000 + 5000 * (day_of_week < 5).astype(float) + np.random.normal(0, 1000, days)
    for i in range(2, days):
        grid_demand[i] += 50 * (oil_price[i - 2] - oil_price[i - 3])

    df = pd.DataFrame({
        "temperature": temperature,
        "humidity": humidity,
        "oil_price": oil_price,
        "gas_price": gas_price,
        "shipping_index": shipping_index,
        "search_trend": search_trend,
        "air_quality": air_quality,
        "grid_demand": grid_demand,
    }, index=dates)

    df.index.name = "timestamp"
    return df
