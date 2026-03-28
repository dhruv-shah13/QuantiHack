"""
EvoAlpha — Data Loader
Loads data from Supabase.

Supabase tables:
  equity_bars    — 50 US stocks, 1yr daily OHLCV
  crypto_bars    — 73 crypto pairs, daily OHLCV
  fx_bars        — 10 FX pairs, 1yr daily OHLCV
  trends_interest — 1000 Google Trends keywords, 5yr weekly
  trends_keywords — keyword metadata (category, source)
"""
import pandas as pd

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
    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client unavailable. Check SUPABASE_URL and keys.")

    # 1. Load target asset OHLCV
    target_col = f"{target_symbol}_close"
    target_df = _load_bars(client, target_symbol, target_asset_class)
    if target_df is None or target_df.empty:
        raise ValueError(f"No data for target {target_symbol} ({target_asset_class}).")

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
        raise ValueError("Merged dataset is empty after joins and forward fill.")

    return merged


def get_available_features(df: pd.DataFrame, target_col: str) -> list[str]:
    """Return list of available feature column names (everything except target)."""
    return [c for c in df.columns if c != target_col]


def list_available_assets() -> dict:
    """
    Query Supabase for all available asset symbols.
    Returns dict with keys 'equity', 'crypto', 'fx', each mapping to a list of dicts.
    """
    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client unavailable. Check SUPABASE_URL and keys.")

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
    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client unavailable. Check SUPABASE_URL and keys.")
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
    if len(symbol) == 6 and symbol.isalpha():
        return "fx"
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


def get_available_features(df: pd.DataFrame, target_col: str) -> list[str]:
    """Return list of available feature column names (everything except target)."""
    return [c for c in df.columns if c != target_col]


def list_available_assets() -> dict:
    """
    Query Supabase for all available asset symbols.
    Returns dict with keys 'equity', 'crypto', 'fx', each mapping to a list of dicts.
    """
    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client unavailable. Check SUPABASE_URL and keys.")

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
    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client unavailable. Check SUPABASE_URL and keys.")
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
    if len(symbol) == 6 and symbol.isalpha():
        return "fx"
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
