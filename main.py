"""
EvoAlpha — Main Entry Point
An evolutionary engine for discovering hidden signals in data.

Usage:
    python main.py                                          # Interactive CLI
    python main.py "Does Google Trends interest in AI predict NVDA stock?"  # CLI with prompt
    python main.py --serve                                  # Start web UI
    python main.py --serve --port 8000                      # Web UI on custom port
"""
import sys
import time

from config.settings import POPULATION_SIZE, NUM_GENERATIONS
from src.data.loader import load_data, get_available_features, list_available_assets
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
        user_prompt = "Does Google Trends interest in AI predict NVDA stock?"
        print(f"  (Using default: '{user_prompt}')")

    print(f"\n📝 Research question: {user_prompt}")

    # --- 2. Parse prompt → target asset + features ---
    print("\n🔍 Parsing research question...")

    # Query available assets from Supabase for smart parsing
    print("  Querying available assets from Supabase...")
    available_assets = list_available_assets()
    n_eq = len(available_assets.get("equity", []))
    n_cr = len(available_assets.get("crypto", []))
    n_fx = len(available_assets.get("fx", []))
    n_tr = len(available_assets.get("trends", []))
    print(f"  📦 Available: {n_eq} equities | {n_cr} crypto | {n_fx} FX | {n_tr} trend keywords")

    parsed = parse_user_prompt(user_prompt, available_assets)

    target_symbol = parsed["target_symbol"]
    target_ac = parsed["target_asset_class"]
    feature_symbols = parsed.get("feature_symbols", [])
    trend_keywords = parsed.get("trend_keywords", [])

    print(f"  🎯 Target: {target_symbol} ({target_ac})")
    if feature_symbols:
        print(f"  📊 Feature assets: {', '.join(feature_symbols)}")
    if trend_keywords:
        print(f"  🔍 Trend keywords: {', '.join(trend_keywords)}")

    # --- 3. Load data ---
    print("\n📊 Loading data...")
    t0 = time.time()

    df = load_data(
        target_symbol=target_symbol,
        target_asset_class=target_ac,
        feature_symbols=feature_symbols,
        trend_keywords=trend_keywords,
    )
    target_col = f"{target_symbol}_close"

    load_time = time.time() - t0
    available_features = get_available_features(df, target_col)

    # Validate
    validation = validate_dataset(df, target_col)
    if not validation["valid"]:
        print(f"  ❌ Data validation failed: {validation['issues']}")
        return

    print(f"  ✅ Loaded {validation['rows']} rows | {len(validation['features'])} features in {load_time:.1f}s")
    print(f"  📅 Date range: {validation['date_range']}")
    print(f"  🎯 Target column: {target_col}")
    print(f"  📋 Features: {', '.join(validation['features'][:10])}")
    if len(validation['features']) > 10:
        print(f"     ... and {len(validation['features']) - 10} more")

    # --- 4. Generate initial hypotheses ---
    print(f"\n🧠 Generating {POPULATION_SIZE} initial hypotheses...")
    t0 = time.time()
    initial_population = generate_hypotheses(
        user_prompt=user_prompt,
        available_features=available_features,
        target=target_col,
        n=POPULATION_SIZE,
    )
    print(f"  Generated {len(initial_population)} strategies in {time.time() - t0:.1f}s")

    # --- 5. Run evolution ---
    print(f"\n🧬 Running evolution ({NUM_GENERATIONS} generations)...")
    print("-" * 70)
    t0 = time.time()

    results = run_evolution(
        df=df,
        features=available_features,
        target=target_col,
        initial_population=initial_population,
        verbose=True,
    )

    elapsed = time.time() - t0
    print("-" * 70)
    print(f"  ✅ Evolution complete in {elapsed:.1f}s")

    # --- 6. Display results ---
    if results["best"] is None:
        print("\n❌ No viable strategies found. Try a different question or more data.")
        return

    # Leaderboard
    print(format_leaderboard(results["leaderboard"]))

    # Evolution history
    print(format_generation_history(results["history"]))

    # --- 7. AI explanation ---
    print("\n🤖 Generating insights...")
    explanation = explain_strategies(results["leaderboard"], target=target_col, top_n=3)
    print(explanation)

    # --- 8. Summary ---
    best = results["best"]
    print("\n" + "=" * 70)
    print(f"🏆 BEST EVOLVED STRATEGY for {target_symbol}")
    print(f"   {best['description']}")
    print(f"   Sharpe: {best['sharpe']:.3f} | PnL: {best['slippage_pnl']:.4%} (after slippage)")
    print(f"   Trades: {best['num_trades']} | Max Drawdown: {best['max_drawdown']:.2%}")
    print("=" * 70)


def serve(port: int = 8000):
    """Start the FastAPI web server for the frontend UI."""
    import uvicorn
    from src.api.routes import app
    print(BANNER)
    print(f"🌐 Starting EvoAlpha web UI on http://localhost:{port}")
    print(f"   Open your browser to http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    if "--serve" in sys.argv:
        port = 8000
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        serve(port)
    else:
        main()
