"""
EvoAlpha — FastAPI API routes with SSE streaming.
Mirrors the CLI pipeline from main.py, streaming progress events to the frontend.
"""
import json
import time
import asyncio

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from config.settings import POPULATION_SIZE, NUM_GENERATIONS
from src.data.loader import load_data, get_available_features, list_available_assets
from src.data.validator import validate_dataset
from src.hypothesis.generator import generate_hypotheses, parse_user_prompt
from src.evolution.engine import run_evolution
from src.leaderboard.ranking import explain_strategies


app = FastAPI(title="EvoAlpha API")

# Serve frontend static files
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/images", StaticFiles(directory="images"), name="images")


@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")


def _strategy_result_to_dict(r: dict) -> dict:
    """Convert a backtest result dict (with Strategy object) to JSON-safe dict."""
    s = r["strategy"]
    return {
        "strategy_id": r["strategy_id"],
        "description": r["description"],
        "feature": s.feature,
        "transform": s.transform,
        "window": s.window,
        "lag": s.lag,
        "signal_type": s.signal_type,
        "threshold": s.threshold,
        "sharpe": r["sharpe"],
        "pnl": r["pnl"],
        "slippage_pnl": r["slippage_pnl"],
        "max_drawdown": r["max_drawdown"],
        "num_trades": r["num_trades"],
    }


@app.get("/api/evolve")
async def evolve_sse(request: Request, hypothesis: str = ""):
    """
    SSE endpoint that runs the full EvoAlpha pipeline and streams progress events.
    Each event has a 'type' field and associated data.
    """
    if not hypothesis.strip():
        hypothesis = "Does Google Trends interest in AI predict NVDA stock?"

    async def event_generator():
        def send(event_type: str, data: dict):
            """Helper to format an SSE event."""
            return {
                "event": event_type,
                "data": json.dumps(data),
            }

        try:
            # ====== PHASE 1: PARSE ======
            yield send("log", {"text": "Initializing EvoAlpha engine...", "type": "highlight"})
            yield send("phase", {"id": "phase-parse", "state": "active"})
            yield send("log", {"text": f'Parsing hypothesis: "{hypothesis}"', "type": "normal"})
            await asyncio.sleep(0.1)

            # Query available assets
            yield send("log", {"text": "Querying available assets from Supabase...", "type": "normal"})
            available_assets = await asyncio.to_thread(list_available_assets)
            n_eq = len(available_assets.get("equity", []))
            n_cr = len(available_assets.get("crypto", []))
            n_fx = len(available_assets.get("fx", []))
            n_tr = len(available_assets.get("trends", []))
            yield send("log", {"text": f"Available: {n_eq} equities | {n_cr} crypto | {n_fx} FX | {n_tr} trend keywords", "type": "normal"})

            parsed = await asyncio.to_thread(parse_user_prompt, hypothesis, available_assets)

            target_symbol = parsed["target_symbol"]
            target_ac = parsed["target_asset_class"]
            feature_symbols = parsed.get("feature_symbols", [])
            trend_keywords = parsed.get("trend_keywords", [])

            yield send("log", {"text": f"Target: {target_symbol} ({target_ac})", "type": "highlight"})
            if feature_symbols:
                yield send("log", {"text": f"Feature assets: {', '.join(feature_symbols)}", "type": "normal"})
            if trend_keywords:
                yield send("log", {"text": f"Trend keywords: {', '.join(trend_keywords)}", "type": "normal"})
            yield send("phase", {"id": "phase-parse", "state": "done"})

            # Check for client disconnect
            if await request.is_disconnected():
                return

            # ====== PHASE 2: LOAD DATA ======
            yield send("phase", {"id": "phase-load", "state": "active"})
            yield send("log", {"text": "Loading data from Supabase...", "type": "normal"})

            t0 = time.time()
            df = await asyncio.to_thread(
                load_data,
                target_symbol=target_symbol,
                target_asset_class=target_ac,
                feature_symbols=feature_symbols,
                trend_keywords=trend_keywords,
            )
            target_col = f"{target_symbol}_close"
            load_time = time.time() - t0
            available_features = get_available_features(df, target_col)

            validation = validate_dataset(df, target_col)
            if not validation["valid"]:
                yield send("log", {"text": f"Data validation failed: {validation['issues']}", "type": "warning"})
                yield send("error", {"message": f"Data validation failed: {validation['issues']}"})
                return

            yield send("log", {"text": f"Loaded {validation['rows']} rows | {len(validation['features'])} features in {load_time:.1f}s", "type": "success"})
            yield send("log", {"text": f"Date range: {validation['date_range']}", "type": "normal"})
            yield send("log", {"text": f"Target: {target_col}", "type": "normal"})
            feat_display = ', '.join(validation['features'][:8])
            extra = f" ... +{len(validation['features']) - 8} more" if len(validation['features']) > 8 else ""
            yield send("log", {"text": f"Features: {feat_display}{extra}", "type": "normal"})
            yield send("phase", {"id": "phase-load", "state": "done"})

            if await request.is_disconnected():
                return

            # ====== PHASE 3: GENERATE HYPOTHESES ======
            yield send("phase", {"id": "phase-generate", "state": "active"})
            yield send("log", {"text": f"Generating {POPULATION_SIZE} initial hypotheses via GPT-4o...", "type": "highlight"})

            t0 = time.time()
            initial_population = await asyncio.to_thread(
                generate_hypotheses,
                user_prompt=hypothesis,
                available_features=available_features,
                target=target_col,
                n=POPULATION_SIZE,
            )
            gen_time = time.time() - t0
            yield send("log", {"text": f"Generated {len(initial_population)} strategies in {gen_time:.1f}s", "type": "success"})
            yield send("stats", {"strategies": len(initial_population)})
            yield send("phase", {"id": "phase-generate", "state": "done"})

            if await request.is_disconnected():
                return

            # ====== PHASE 4: EVOLUTION ======
            yield send("phase", {"id": "phase-evolve", "state": "active"})
            yield send("log", {"text": f"Starting evolution ({NUM_GENERATIONS} generations)...", "type": "highlight"})
            yield send("log", {"text": "Selection: top 50% → Mutation → Crossover", "type": "normal"})

            # Run evolution in a thread (it's CPU-bound)
            # We need generation-by-generation progress, so we use a custom callback approach
            t0 = time.time()
            results = await asyncio.to_thread(
                run_evolution,
                df=df,
                features=available_features,
                target=target_col,
                initial_population=initial_population,
                verbose=True,
            )
            evo_time = time.time() - t0

            # Stream history after evolution completes
            total_evaluated = 0
            for h in results["history"]:
                total_evaluated += h["alive"]
                yield send("generation", {
                    "gen": h["generation"],
                    "alive": h["alive"],
                    "best_sharpe": h["best_sharpe"],
                    "avg_sharpe": h["avg_sharpe"],
                    "best_pnl": h["best_pnl"],
                    "best_strategy": h["best_strategy"],
                })
                yield send("stats", {
                    "generation": h["generation"] + 1,
                    "strategies": h["alive"],
                    "sharpe": h["best_sharpe"],
                    "pnl": h["best_pnl"],
                })
                yield send("log", {
                    "text": f"Gen {h['generation']:>2} | Alive: {h['alive']:>3} | Best Sharpe: {h['best_sharpe']:>7.3f} | Avg Sharpe: {h['avg_sharpe']:>7.3f} | Best PnL: {h['best_pnl']:>9.4%}",
                    "type": "normal"
                })
                await asyncio.sleep(0.15)  # Small delay for streaming effect

            yield send("log", {"text": f"Evolution complete in {evo_time:.1f}s", "type": "success"})
            yield send("phase", {"id": "phase-evolve", "state": "done"})

            if await request.is_disconnected():
                return

            if results["best"] is None:
                yield send("log", {"text": "No viable strategies found. Try a different question.", "type": "warning"})
                yield send("error", {"message": "No viable strategies found."})
                return

            # ====== PHASE 5: EXPLAIN ======
            yield send("phase", {"id": "phase-explain", "state": "active"})
            yield send("log", {"text": "Generating AI insights via GPT-4o...", "type": "highlight"})

            explanation = await asyncio.to_thread(
                explain_strategies, results["leaderboard"], target=target_col, top_n=3
            )
            yield send("log", {"text": "Insights generated", "type": "success"})
            yield send("phase", {"id": "phase-explain", "state": "done"})

            # ====== FINAL RESULTS ======
            leaderboard = [_strategy_result_to_dict(r) for r in results["leaderboard"][:10]]
            best = _strategy_result_to_dict(results["best"])

            yield send("results", {
                "best": best,
                "leaderboard": leaderboard,
                "history": results["history"],
                "explanation": explanation,
                "generations": NUM_GENERATIONS,
                "total_evaluated": total_evaluated,
            })

        except Exception as e:
            yield send("log", {"text": f"Error: {str(e)}", "type": "warning"})
            yield send("error", {"message": str(e)})

    return EventSourceResponse(event_generator())
