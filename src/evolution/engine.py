"""
EvoAlpha — Evolution Engine
The main loop: generate → evaluate → select → mutate → repeat.
"""
import pandas as pd
from src.strategy.code_generator import Strategy, random_population
from src.strategy.filter import filter_population
from src.backtesting.engine import backtest_population
from src.evolution.selection import select_survivors
from src.evolution.population import create_next_generation
from config.settings import POPULATION_SIZE, NUM_GENERATIONS


def run_evolution(
    df: pd.DataFrame,
    features: list[str],
    target: str = "oil_price",
    initial_population: list[Strategy] | None = None,
    population_size: int = POPULATION_SIZE,
    num_generations: int = NUM_GENERATIONS,
    verbose: bool = True,
) -> dict:
    """
    Run the full evolutionary loop.
    
    Args:
        df: merged dataset with features + target
        features: list of feature column names
        target: target variable column name
        initial_population: optional pre-generated strategies (e.g. from LLM)
        population_size: how many strategies per generation
        num_generations: how many generations to evolve
        verbose: print progress to CLI
    
    Returns:
        dict with:
            - 'best': top strategy result
            - 'leaderboard': sorted list of all-time best results
            - 'history': list of per-generation stats
    """
    # --- Seed the population ---
    if initial_population is not None:
        population = initial_population
    else:
        population = random_population(features, population_size, generation=0)

    all_time_best: list[dict] = []
    history: list[dict] = []

    for gen in range(num_generations):
        # Filter out invalid strategies
        population = filter_population(population, features)

        # If population got too small, refill with randoms
        while len(population) < population_size // 2:
            from src.strategy.code_generator import random_strategy
            population.append(random_strategy(features, gen))

        # Evaluate
        results = backtest_population(population, df, target)

        if len(results) == 0:
            if verbose:
                print(f"  Gen {gen}: No valid strategies. Reseeding...")
            population = random_population(features, population_size, gen)
            continue

        # Track stats
        best_sharpe = results[0]["sharpe"]
        avg_sharpe = sum(r["sharpe"] for r in results) / len(results)
        best_pnl = results[0]["slippage_pnl"]

        gen_stats = {
            "generation": gen,
            "alive": len(results),
            "best_sharpe": round(best_sharpe, 4),
            "avg_sharpe": round(avg_sharpe, 4),
            "best_pnl": round(best_pnl, 6),
            "best_strategy": results[0]["description"],
        }
        history.append(gen_stats)

        if verbose:
            print(
                f"  Gen {gen:>2} | "
                f"Alive: {len(results):>3} | "
                f"Best Sharpe: {best_sharpe:>7.3f} | "
                f"Avg Sharpe: {avg_sharpe:>7.3f} | "
                f"Best PnL: {best_pnl:>9.4%}"
            )

        # Merge into all-time leaderboard (keep unique by strategy ID)
        seen_ids = {r["strategy_id"] for r in all_time_best}
        for r in results:
            if r["strategy_id"] not in seen_ids:
                all_time_best.append(r)
                seen_ids.add(r["strategy_id"])

        # Select survivors
        survivors = select_survivors(results)

        # Create next generation
        population = create_next_generation(survivors, features, gen + 1)

    # Final leaderboard: sort all-time best, deduplicate by description
    all_time_best.sort(key=lambda r: r["slippage_pnl"], reverse=True)
    seen_descriptions = set()
    leaderboard = []
    for r in all_time_best:
        if r["description"] not in seen_descriptions:
            leaderboard.append(r)
            seen_descriptions.add(r["description"])
        if len(leaderboard) >= 20:
            break

    return {
        "best": leaderboard[0] if leaderboard else None,
        "leaderboard": leaderboard,
        "history": history,
    }
