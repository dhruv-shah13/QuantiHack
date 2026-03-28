"""
EvoAlpha — Mutation Operators
Randomly tweak one or more parameters of a strategy.
"""
import random
from src.strategy.code_generator import Strategy, _make_id
from config.settings import TRANSFORMS, WINDOWS, LAGS, SIGNAL_TYPES, MUTATION_RATE


def mutate(strategy: Strategy, features: list[str], generation: int) -> Strategy:
    """
    Create a mutated child from a parent strategy.
    Each parameter has MUTATION_RATE chance of being tweaked.
    """
    child = strategy.clone()
    child.id = _make_id()
    child.generation = generation
    child.parent_ids = [strategy.id]

    # Feature
    if random.random() < MUTATION_RATE:
        child.feature = random.choice(features)

    # Transform
    if random.random() < MUTATION_RATE:
        child.transform = random.choice(TRANSFORMS)

    # Window — nudge rather than replace
    if random.random() < MUTATION_RATE:
        current_idx = WINDOWS.index(child.window) if child.window in WINDOWS else 0
        delta = random.choice([-1, 1])
        new_idx = max(0, min(len(WINDOWS) - 1, current_idx + delta))
        child.window = WINDOWS[new_idx]

    # Lag — nudge
    if random.random() < MUTATION_RATE:
        current_idx = LAGS.index(child.lag) if child.lag in LAGS else 0
        delta = random.choice([-1, 1])
        new_idx = max(0, min(len(LAGS) - 1, current_idx + delta))
        child.lag = LAGS[new_idx]

    # Signal type
    if random.random() < MUTATION_RATE:
        child.signal_type = random.choice(SIGNAL_TYPES)

    # Threshold — continuous perturbation
    if random.random() < MUTATION_RATE:
        if child.signal_type == "percentile":
            child.threshold = max(10, min(95, child.threshold + random.uniform(-10, 10)))
        else:
            child.threshold += random.uniform(-0.3, 0.3)
        child.threshold = round(child.threshold, 4)

    return child
