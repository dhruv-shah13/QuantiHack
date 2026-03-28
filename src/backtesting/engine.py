"""
EvoAlpha — Backtesting Engine
Takes a Strategy + DataFrame → returns performance metrics.
"""
import pandas as pd
import numpy as np
from src.strategy.code_generator import Strategy
from src.data.feature_engineering import apply_transform, generate_signal
from src.backtesting.metrics import compute_all_metrics


def backtest_strategy(strategy: Strategy, df: pd.DataFrame, target: str = "oil_price") -> dict | None:
    """
    Backtest a single strategy against the dataset.
    
    Args:
        strategy: Strategy object with DNA parameters
        df: DataFrame with feature columns + target column, DatetimeIndex
        target: name of the target column
    
    Returns:
        dict with strategy info + all metrics, or None if strategy fails
    """
    try:
        # 1. Check feature exists
        if strategy.feature not in df.columns:
            return None

        feature_series = df[strategy.feature]

        # 2. Apply transform
        transformed = apply_transform(feature_series, strategy.transform, strategy.window)

        # 3. Apply lag
        transformed = transformed.shift(strategy.lag)

        # 4. Generate signal
        signal = generate_signal(transformed, strategy.signal_type, strategy.threshold)

        # 5. Compute target returns
        target_returns = df[target].pct_change()

        # 6. Strategy returns = signal (shifted by 1 to avoid lookahead) * target returns
        strategy_returns = signal.shift(1) * target_returns

        # 7. Drop NaN rows
        valid = strategy_returns.dropna()
        valid_signal = signal.reindex(valid.index).fillna(0)

        if len(valid) < 30:
            return None  # Not enough data to evaluate

        # 8. Compute metrics
        metrics = compute_all_metrics(valid, valid_signal)

        return {
            "strategy": strategy,
            "strategy_id": strategy.id,
            "description": strategy.describe(),
            **metrics,
        }

    except Exception:
        return None


def backtest_population(
    population: list[Strategy], df: pd.DataFrame, target: str = "oil_price"
) -> list[dict]:
    """
    Backtest an entire population. Returns sorted results (best Sharpe first).
    Strategies that fail are silently dropped.
    """
    results = []
    for strategy in population:
        result = backtest_strategy(strategy, df, target)
        if result is not None:
            results.append(result)

    # Sort by slippage-adjusted PnL (the real metric)
    results.sort(key=lambda r: r["slippage_pnl"], reverse=True)
    return results
