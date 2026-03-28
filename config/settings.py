"""
EvoAlpha — Configuration Settings
All tuneable parameters in one place.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "True").lower() in ("true", "1", "yes")

# --- Evolution Parameters ---
POPULATION_SIZE = 20          # strategies per generation
NUM_GENERATIONS = 10          # evolution rounds
SURVIVAL_RATE = 0.5           # top 50% survive
MUTATION_RATE = 0.3           # chance each parameter mutates
CROSSOVER_RATE = 0.4          # chance of crossover vs mutation

# --- Strategy Parameter Space ---
TRANSFORMS = ["rolling_mean", "z_score", "rate_of_change", "raw"]
WINDOWS = [3, 5, 7, 10, 14, 21]
LAGS = [1, 2, 3, 5]
SIGNAL_TYPES = ["threshold", "crossover", "percentile"]

# --- Backtesting ---
SLIPPAGE_BPS = 5              # 5 basis points per trade
ANNUALIZATION_FACTOR = 252    # trading days per year
