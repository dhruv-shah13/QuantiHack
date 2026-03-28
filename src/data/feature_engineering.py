"""
EvoAlpha — Feature Engineering
Applies transforms to raw features based on strategy parameters.
This is the bridge between strategy DNA and backtestable signals.
"""
import pandas as pd
import numpy as np


def apply_transform(series: pd.Series, transform: str, window: int) -> pd.Series:
    """
    Apply a named transform to a feature series.
    
    Args:
        series: raw feature data
        transform: one of 'rolling_mean', 'z_score', 'rate_of_change', 'raw'
        window: lookback window for the transform
    
    Returns:
        Transformed series (same index, may have leading NaNs)
    """
    if transform == "rolling_mean":
        return series.rolling(window=window).mean()
    
    elif transform == "z_score":
        rolling_mean = series.rolling(window=window).mean()
        rolling_std = series.rolling(window=window).std()
        return (series - rolling_mean) / rolling_std.replace(0, np.nan)
    
    elif transform == "rate_of_change":
        return series.pct_change(periods=window)
    
    elif transform == "raw":
        return series.copy()
    
    else:
        raise ValueError(f"Unknown transform: {transform}")


def generate_signal(transformed: pd.Series, signal_type: str, threshold: float) -> pd.Series:
    """
    Convert a transformed feature into a binary signal (1 = long, 0 = flat).
    
    Args:
        transformed: the transformed feature series
        signal_type: one of 'threshold', 'crossover', 'percentile'
        threshold: the trigger value
    
    Returns:
        Binary signal series (1/0)
    """
    if signal_type == "threshold":
        return (transformed > threshold).astype(int)
    
    elif signal_type == "crossover":
        # Signal when short MA crosses above long MA
        short_ma = transformed.rolling(window=3).mean()
        long_ma = transformed.rolling(window=max(7, int(threshold))).mean()
        return (short_ma > long_ma).astype(int)
    
    elif signal_type == "percentile":
        # Signal when value is above Nth percentile (threshold = percentile, e.g. 75)
        pct = threshold if 0 < threshold < 100 else 75
        rolling_pct = transformed.rolling(window=50, min_periods=10).quantile(pct / 100)
        return (transformed > rolling_pct).astype(int)
    
    else:
        raise ValueError(f"Unknown signal_type: {signal_type}")
