"""
EvoAlpha — Crossover / Recombination
Combine two parent strategies to produce a child.
"""
import random
from src.strategy.code_generator import Strategy, _make_id


def crossover(parent1: Strategy, parent2: Strategy, generation: int) -> Strategy:
    """
    Uniform crossover: for each parameter, randomly pick from parent1 or parent2.
    """
    child = Strategy(
        feature=random.choice([parent1.feature, parent2.feature]),
        transform=random.choice([parent1.transform, parent2.transform]),
        window=random.choice([parent1.window, parent2.window]),
        lag=random.choice([parent1.lag, parent2.lag]),
        signal_type=random.choice([parent1.signal_type, parent2.signal_type]),
        threshold=random.choice([parent1.threshold, parent2.threshold]),
        id=_make_id(),
        generation=generation,
        parent_ids=[parent1.id, parent2.id],
    )
    return child
