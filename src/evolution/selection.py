"""
EvoAlpha — Selection Operators
Choose which strategies survive to the next generation.
"""
from config.settings import SURVIVAL_RATE


def select_survivors(results: list[dict]) -> list[dict]:
    """
    Keep the top SURVIVAL_RATE fraction of the population.
    Results should already be sorted (best first).
    
    Returns:
        list of result dicts that survived
    """
    n_keep = max(2, int(len(results) * SURVIVAL_RATE))
    return results[:n_keep]


def tournament_select(results: list[dict], k: int = 3) -> dict:
    """
    Tournament selection: pick k random candidates, return the best.
    """
    import random
    candidates = random.sample(results, min(k, len(results)))
    return max(candidates, key=lambda r: r["slippage_pnl"])
