"""
EvoAlpha — Population Manager
Creates the next generation from survivors via mutation + crossover.
"""
import random
from src.strategy.code_generator import Strategy, random_strategy
from src.evolution.mutation import mutate
from src.evolution.recombination import crossover
from src.evolution.selection import tournament_select
from config.settings import CROSSOVER_RATE, POPULATION_SIZE


def create_next_generation(
    survivors: list[dict],
    features: list[str],
    generation: int,
) -> list[Strategy]:
    """
    Produce a new generation of POPULATION_SIZE strategies.
    
    - Elite strategies are carried forward unchanged
    - Remaining slots filled by mutation or crossover of survivors
    - A few completely new random strategies for diversity
    """
    new_population: list[Strategy] = []

    # 1. Elitism: top 2 strategies survive unchanged
    for result in survivors[:2]:
        elite = result["strategy"].clone()
        elite.generation = generation
        new_population.append(elite)

    # 2. Fill remaining via mutation/crossover
    n_breed = POPULATION_SIZE - len(new_population) - 2  # save 2 slots for randoms
    for _ in range(max(0, n_breed)):
        if random.random() < CROSSOVER_RATE and len(survivors) >= 2:
            # Crossover
            p1 = tournament_select(survivors)["strategy"]
            p2 = tournament_select(survivors)["strategy"]
            child = crossover(p1, p2, generation)
        else:
            # Mutation
            parent = tournament_select(survivors)["strategy"]
            child = mutate(parent, features, generation)
        new_population.append(child)

    # 3. Inject 2 random immigrants for diversity
    for _ in range(2):
        new_population.append(random_strategy(features, generation))

    return new_population
