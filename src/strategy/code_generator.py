"""
EvoAlpha — Strategy Schema & Generator
Defines the DNA of a strategy and how to create random ones.
"""
import random
import copy
from dataclasses import dataclass, field, asdict
from config.settings import TRANSFORMS, WINDOWS, LAGS, SIGNAL_TYPES


@dataclass
class Strategy:
    """
    The DNA of an evolved strategy.
    6 parameters define what the strategy does.
    """
    feature: str              # which data column to use
    transform: str            # rolling_mean | z_score | rate_of_change | raw
    window: int               # lookback period for transform
    lag: int                  # days to shift signal
    signal_type: str          # threshold | crossover | percentile
    threshold: float          # trigger value for signal generation
    id: str = ""              # unique identifier
    generation: int = 0       # which generation it was born in
    parent_ids: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def clone(self) -> "Strategy":
        return copy.deepcopy(self)

    def describe(self) -> str:
        """Human-readable one-liner."""
        return (
            f"{self.transform}({self.feature}, w={self.window}) "
            f"→ lag {self.lag}d → {self.signal_type}(t={self.threshold:.2f})"
        )


def _make_id() -> str:
    """Generate a short unique strategy ID."""
    return f"S-{random.randint(10000, 99999)}"


def random_strategy(features: list[str], generation: int = 0) -> Strategy:
    """
    Generate a single random strategy given available features.
    
    Args:
        features: list of available feature column names
        generation: the current generation number
    """
    feature = random.choice(features)
    transform = random.choice(TRANSFORMS)

    # Set threshold range based on transform
    if transform == "z_score":
        threshold = round(random.uniform(-2.0, 2.0), 2)
    elif transform == "rate_of_change":
        threshold = round(random.uniform(-0.05, 0.05), 4)
    elif transform == "rolling_mean":
        # This will be data-dependent; use a generic range
        threshold = round(random.uniform(-1.0, 1.0), 2)
    else:
        threshold = round(random.uniform(-1.0, 1.0), 2)

    signal_type = random.choice(SIGNAL_TYPES)
    if signal_type == "percentile":
        threshold = round(random.uniform(25, 90), 1)

    return Strategy(
        feature=feature,
        transform=transform,
        window=random.choice(WINDOWS),
        lag=random.choice(LAGS),
        signal_type=signal_type,
        threshold=threshold,
        id=_make_id(),
        generation=generation,
    )


def random_population(features: list[str], size: int = 20, generation: int = 0) -> list[Strategy]:
    """Generate an initial random population of strategies."""
    return [random_strategy(features, generation) for _ in range(size)]
