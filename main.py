"""
EvoAlpha — Main Entry Point
An evolutionary engine for discovering hidden signals in data.

Usage:
    python main.py
    python main.py "Does temperature affect oil prices?"
"""
import sys
import time

from config.settings import POPULATION_SIZE, NUM_GENERATIONS, USE_MOCK_DATA
from src.data.loader import load_data, get_available_features
from src.data.validator import validate_dataset
from src.hypothesis.generator import generate_hypotheses, parse_user_prompt
from src.evolution.engine import run_evolution
from src.leaderboard.ranking import format_leaderboard, format_generation_history, explain_strategies


BANNER = """
╔══════════════════════════════════════════════════════╗
║              🧬 EvoAlpha v0.1                        ║
║   Evolutionary Engine for Discovering Hidden Signals ║
╚══════════════════════════════════════════════════════╝
"""


def main():
    print(BANNER)

    # --- 1. Get user prompt ---
    if len(sys.argv) > 1:
        user_prompt = " ".join(sys.argv[1:])
    else:
        user_prompt = input("🔬 Enter your research question:\n> ").strip()

    if not user_prompt:
        user_prompt = "Does temperature affect oil prices?"
        print(f"  (Using default: '{user_prompt}')")

    print(f"\n📝 Research question: {user_prompt}")

    # --- 2. Load data ---
    print("\n📊 Loading data...")
    if USE_MOCK_DATA:
        print("  Using mock data (set USE_MOCK_DATA=False for Supabase)")
    
    df = load_data()
    available_features = get_available_features()
    
    # Parse prompt to identify target
    parsed = parse_user_prompt(user_prompt, available_features)
    target = parsed["target_hint"]
    
    # Validate
    validation = validate_dataset(df, target)
    if not validation["valid"]:
        print(f"  ❌ Data validation failed: {validation['issues']}")
        return
    
    print(f"  ✅ Loaded {validation['rows']} rows | {len(validation['features'])} features")
    print(f"  📅 Date range: {validation['date_range']}")
    print(f"  🎯 Target: {target}")
    print(f"  📋 Features: {', '.join(validation['features'])}")

    # --- 3. Generate initial hypotheses ---
    print(f"\n🧠 Generating {POPULATION_SIZE} initial hypotheses...")
    t0 = time.time()
    initial_population = generate_hypotheses(
        user_prompt=user_prompt,
        available_features=available_features,
        target=target,
        n=POPULATION_SIZE,
    )
    print(f"  Generated {len(initial_population)} strategies in {time.time() - t0:.1f}s")

    # --- 4. Run evolution ---
    print(f"\n🧬 Running evolution ({NUM_GENERATIONS} generations)...")
    print("-" * 70)
    t0 = time.time()
    
    results = run_evolution(
        df=df,
        features=available_features,
        target=target,
        initial_population=initial_population,
        verbose=True,
    )
    
    elapsed = time.time() - t0
    print("-" * 70)
    print(f"  ✅ Evolution complete in {elapsed:.1f}s")

    # --- 5. Display results ---
    if results["best"] is None:
        print("\n❌ No viable strategies found. Try a different question or more data.")
        return

    # Leaderboard
    print(format_leaderboard(results["leaderboard"]))

    # Evolution history
    print(format_generation_history(results["history"]))

    # --- 6. AI explanation ---
    print("\n🤖 Generating insights...")
    explanation = explain_strategies(results["leaderboard"], target=target, top_n=3)
    print(explanation)

    # --- 7. Summary ---
    best = results["best"]
    print("\n" + "=" * 70)
    print("🏆 BEST EVOLVED STRATEGY")
    print(f"   {best['description']}")
    print(f"   Sharpe: {best['sharpe']:.3f} | PnL: {best['slippage_pnl']:.4%} (after slippage)")
    print(f"   Trades: {best['num_trades']} | Max Drawdown: {best['max_drawdown']:.2%}")
    print("=" * 70)


if __name__ == "__main__":
    main()
