"""
EvoAlpha — Data Loader
Loads data from Supabase or generates mock data for development.
"""
import pandas as pd
import numpy as np
from config.settings import USE_MOCK_DATA


def load_data(features: list[str] | None = None, target: str = "oil_price") -> pd.DataFrame:
    """
    Main entry point: returns a clean DataFrame indexed by timestamp.
    Columns = feature columns + target column. Daily frequency.
    
    Args:
        features: list of feature column names to include (None = all)
        target: the target variable column name
    
    Returns:
        pd.DataFrame indexed by datetime with no missing values
    """
    if USE_MOCK_DATA:
        df = _generate_mock_data()
    else:
        from src.supabase.client import get_supabase_client
        df = _load_from_supabase()

    # Filter to requested features + target
    if features is not None:
        cols = [c for c in features if c in df.columns]
        if target in df.columns:
            cols.append(target)
        df = df[cols]

    return df


def get_available_features(target: str = "oil_price") -> list[str]:
    """Return list of available feature column names (everything except target)."""
    df = load_data(target=target)
    return [c for c in df.columns if c != target]


def _load_from_supabase() -> pd.DataFrame:
    """
    Pull merged dataset from Supabase.
    Your teammate will fill this in once Supabase tables are ready.
    """
    from src.supabase.client import get_supabase_client
    client = get_supabase_client()
    
    # TODO: Replace with actual table name once Supabase is set up
    response = client.table("merged_data").select("*").execute()
    df = pd.DataFrame(response.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df = df.ffill().dropna()
    return df


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
    # Inject a subtle real signal: temperature anomalies 3 days prior affect oil
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

    # --- Air quality index (seasonal, inversely related to industrial activity) ---
    air_quality = 40 + 15 * np.sin(2 * np.pi * day_of_year / 365 + np.pi) + np.random.normal(0, 8, days)

    # --- Grid demand (industrial proxy, weekly cycle) ---
    day_of_week = np.arange(days) % 7
    grid_demand = 30000 + 5000 * (day_of_week < 5).astype(float) + np.random.normal(0, 1000, days)
    # Slight positive correlation with oil price moves
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
