"""
EvoAlpha — Strategy Filter
Validates strategies before backtesting.
"""
from src.strategy.code_generator import Strategy
from config.settings import TRANSFORMS, WINDOWS, LAGS, SIGNAL_TYPES


def is_valid_strategy(strategy: Strategy, features: list[str]) -> bool:
    """
    Check that a strategy has valid DNA parameters.
    Returns True if the strategy is usable.
    """
    if strategy.feature not in features:
        return False
    if strategy.transform not in TRANSFORMS:
        return False
    if strategy.window not in WINDOWS:
        return False
    if strategy.lag not in LAGS:
        return False
    if strategy.signal_type not in SIGNAL_TYPES:
        return False
    return True


def filter_population(population: list[Strategy], features: list[str]) -> list[Strategy]:
    """Remove invalid strategies from a population."""
    return [s for s in population if is_valid_strategy(s, features)]
