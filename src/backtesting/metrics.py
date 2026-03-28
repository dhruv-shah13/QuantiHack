"""
EvoAlpha — Performance Metrics
Sharpe ratio, PnL, slippage-adjusted PnL, max drawdown.
"""
import numpy as np
import pandas as pd
from config.settings import SLIPPAGE_BPS, ANNUALIZATION_FACTOR


def sharpe_ratio(returns: pd.Series) -> float:
    """Annualized Sharpe ratio. Returns 0.0 if std is 0."""
    if returns.std() == 0 or np.isnan(returns.std()):
        return 0.0
    return float((returns.mean() / returns.std()) * np.sqrt(ANNUALIZATION_FACTOR))


def cumulative_pnl(returns: pd.Series) -> float:
    """Total cumulative PnL (as a fraction, e.g. 0.15 = 15%)."""
    return float((1 + returns).prod() - 1)


def slippage_adjusted_pnl(returns: pd.Series, signal: pd.Series) -> float:
    """
    PnL after deducting transaction costs.
    Every time the signal flips (0→1 or 1→0), we charge SLIPPAGE_BPS.
    """
    raw_pnl = cumulative_pnl(returns)
    num_trades = int((signal.diff().abs() > 0).sum())
    cost = num_trades * (SLIPPAGE_BPS / 10000)
    return float(raw_pnl - cost)


def num_trades(signal: pd.Series) -> int:
    """Count the number of signal flips (trades)."""
    return int((signal.diff().abs() > 0).sum())


def max_drawdown(returns: pd.Series) -> float:
    """Maximum peak-to-trough drawdown."""
    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    return float(drawdown.min())


def compute_all_metrics(strategy_returns: pd.Series, signal: pd.Series) -> dict:
    """Compute all metrics at once and return as a dict."""
    return {
        "sharpe": round(sharpe_ratio(strategy_returns), 4),
        "pnl": round(cumulative_pnl(strategy_returns), 6),
        "slippage_pnl": round(slippage_adjusted_pnl(strategy_returns, signal), 6),
        "max_drawdown": round(max_drawdown(strategy_returns), 6),
        "num_trades": num_trades(signal),
    }
