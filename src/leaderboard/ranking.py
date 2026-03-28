"""
EvoAlpha — Leaderboard & Explainer Agent (OpenAI GPT-4o)
Ranks strategies and generates natural language explanations.
"""
import json
from config.settings import OPENAI_API_KEY


def format_leaderboard(results: list[dict], top_n: int = 10) -> str:
    """
    Format the leaderboard as a pretty CLI table.
    """
    if not results:
        return "No strategies survived evolution."

    lines = []
    lines.append("")
    lines.append("🏆 EvoAlpha Leaderboard")
    lines.append("=" * 90)
    lines.append(
        f"{'Rank':<5} {'ID':<10} {'Sharpe':>8} {'PnL':>10} {'Adj PnL':>10} "
        f"{'Trades':>7} {'MaxDD':>8}  Strategy"
    )
    lines.append("-" * 90)

    for i, r in enumerate(results[:top_n]):
        lines.append(
            f"{i+1:<5} {r['strategy_id']:<10} {r['sharpe']:>8.3f} "
            f"{r['pnl']:>9.4%} {r['slippage_pnl']:>9.4%} "
            f"{r['num_trades']:>7} {r['max_drawdown']:>7.2%}  "
            f"{r['description']}"
        )

    lines.append("=" * 90)
    return "\n".join(lines)


def format_generation_history(history: list[dict]) -> str:
    """Format the generation-by-generation evolution history."""
    if not history:
        return "No evolution history."

    lines = []
    lines.append("")
    lines.append("📈 Evolution History")
    lines.append("-" * 70)
    lines.append(f"{'Gen':<5} {'Alive':>6} {'Best Sharpe':>12} {'Avg Sharpe':>12} {'Best PnL':>12}")
    lines.append("-" * 70)

    for h in history:
        lines.append(
            f"{h['generation']:<5} {h['alive']:>6} "
            f"{h['best_sharpe']:>12.4f} {h['avg_sharpe']:>12.4f} "
            f"{h['best_pnl']:>11.4%}"
        )

    lines.append("-" * 70)
    return "\n".join(lines)


def explain_strategies(results: list[dict], target: str = "oil_price", top_n: int = 3) -> str:
    """
    Use Gemini to generate natural language explanations of top strategies.
    Falls back to template-based explanations if Gemini is unavailable.
    """
    if not results:
        return "No strategies to explain."

    if not OPENAI_API_KEY:
        return _template_explain(results[:top_n], target)

    try:
        return _openai_explain(results[:top_n], target)
    except Exception as e:
        print(f"  ⚠ OpenAI explainer failed ({e}) — using template")
        return _template_explain(results[:top_n], target)


def _openai_explain(results: list[dict], target: str) -> str:
    """Use OpenAI GPT-4o to generate insightful explanations."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build strategy summaries for the prompt
    strategy_summaries = []
    for i, r in enumerate(results):
        s = r["strategy"]
        summary = {
            "rank": i + 1,
            "feature": s.feature,
            "transform": s.transform,
            "window": s.window,
            "lag": s.lag,
            "signal_type": s.signal_type,
            "threshold": s.threshold,
            "sharpe_ratio": r["sharpe"],
            "pnl": f"{r['pnl']:.4%}",
            "slippage_adjusted_pnl": f"{r['slippage_pnl']:.4%}",
            "num_trades": r["num_trades"],
        }
        strategy_summaries.append(summary)

    prompt = f"""You are a quant research analyst explaining evolved trading strategies to a hackathon audience.

These strategies were EVOLVED (not hand-designed) by an evolutionary algorithm called EvoAlpha.
They attempt to predict movements in {target} using various features.

Here are the top evolved strategies:

{json.dumps(strategy_summaries, indent=2)}

For each strategy, write:
1. A clear 1-2 sentence explanation of what the strategy does in plain English
2. WHY this relationship might exist in the real world (even if speculative)
3. One surprising insight or pattern across the top strategies

Be concise, insightful, and engaging. This is for a live demo.
Format with emoji and clear headers."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a quant research analyst. Be concise and insightful."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
    )

    return "\n🧠 AI Analysis\n" + response.choices[0].message.content


def _template_explain(results: list[dict], target: str) -> str:
    """Fallback template-based explanations when Gemini is unavailable."""
    lines = ["\n🧠 Strategy Insights (template mode)\n"]

    for i, r in enumerate(results):
        s = r["strategy"]
        transform_desc = {
            "rolling_mean": f"{s.window}-day moving average",
            "z_score": f"{s.window}-day z-score",
            "rate_of_change": f"{s.window}-day rate of change",
            "raw": "raw value",
        }.get(s.transform, s.transform)

        signal_desc = {
            "threshold": f"exceeds {s.threshold:.2f}",
            "crossover": "short-term trend crosses above long-term",
            "percentile": f"rises above the {s.threshold:.0f}th percentile",
        }.get(s.signal_type, s.signal_type)

        lines.append(
            f"  #{i+1} | {s.id}\n"
            f"    Uses the {transform_desc} of {s.feature}, lagged by {s.lag} day(s).\n"
            f"    Enters a long position when the signal {signal_desc}.\n"
            f"    Performance: Sharpe {r['sharpe']:.3f} | PnL {r['slippage_pnl']:.4%} (after slippage)\n"
        )

    return "\n".join(lines)
