"""
EvoAlpha — Hypothesis Generator (OpenAI GPT-4o Agent)
Takes a user prompt + available features → generates an initial population of strategies.
Falls back to random generation if OpenAI is unavailable.
"""
import json
import random
from src.strategy.code_generator import Strategy, _make_id, random_population
from config.settings import OPENAI_API_KEY, TRANSFORMS, WINDOWS, LAGS, SIGNAL_TYPES


SYSTEM_PROMPT = """You are a quantitative research assistant for EvoAlpha, an evolutionary strategy engine.

Given a user's research question and a list of available data features, generate diverse trading strategy hypotheses.

Each strategy must be a JSON object with EXACTLY these fields:
- "feature": one of the available features (string)
- "transform": one of {transforms}
- "window": one of {windows}
- "lag": one of {lags}
- "signal_type": one of {signal_types}
- "threshold": a float (for z_score: between -2 and 2; for rate_of_change: between -0.05 and 0.05; for percentile signal_type: between 20 and 90)

Generate {n} diverse strategies. Vary the features, transforms, and parameters.
Think about what real-world relationships might exist between the features and the target.

Respond with ONLY a JSON array of strategy objects. No explanation, no markdown."""


def generate_hypotheses(
    user_prompt: str,
    available_features: list[str],
    target: str = "AAPL_close",
    n: int = 20,
) -> list[Strategy]:
    """
    Use OpenAI GPT-4o to generate an initial population of strategies from a user prompt.
    Falls back to random generation if OpenAI is unavailable or fails.
    """
    if not OPENAI_API_KEY:
        print("  ⚠ No OpenAI API key — using random strategy generation")
        return random_population(available_features, n, generation=0)

    try:
        return _generate_with_openai(user_prompt, available_features, target, n)
    except Exception as e:
        print(f"  ⚠ OpenAI failed ({e}) — falling back to random generation")
        return random_population(available_features, n, generation=0)


def _generate_with_openai(
    user_prompt: str,
    available_features: list[str],
    target: str,
    n: int,
) -> list[Strategy]:
    """Call OpenAI GPT-4o to generate strategies."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    system_prompt = SYSTEM_PROMPT.format(
        transforms=TRANSFORMS,
        windows=WINDOWS,
        lags=LAGS,
        signal_types=SIGNAL_TYPES,
        n=n,
    )

    user_message = (
        f"Research question: {user_prompt}\n"
        f"Available features: {available_features}\n"
        f"Target variable: {target}\n"
        f"Generate {n} diverse strategy hypotheses."
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.9,
        max_tokens=4096,
    )

    # Parse the JSON response
    text = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    raw_strategies = json.loads(text)

    # Convert to Strategy objects with validation
    strategies = []
    for raw in raw_strategies:
        try:
            s = Strategy(
                feature=raw["feature"] if raw["feature"] in available_features else random.choice(available_features),
                transform=raw["transform"] if raw["transform"] in TRANSFORMS else random.choice(TRANSFORMS),
                window=raw["window"] if raw["window"] in WINDOWS else random.choice(WINDOWS),
                lag=raw["lag"] if raw["lag"] in LAGS else random.choice(LAGS),
                signal_type=raw["signal_type"] if raw["signal_type"] in SIGNAL_TYPES else random.choice(SIGNAL_TYPES),
                threshold=float(raw["threshold"]),
                id=_make_id(),
                generation=0,
            )
            strategies.append(s)
        except (KeyError, ValueError):
            continue

    # If we got fewer than expected, pad with randoms
    while len(strategies) < n:
        strategies.append(random_population(available_features, 1, generation=0)[0])

    return strategies[:n]


# ─────────────────────────────────────────────
# Prompt parsing — resolve user question to target + features
# ─────────────────────────────────────────────

# Well-known ticker / name mappings for rule-based fallback
_EQUITY_ALIASES = {
    "apple": "AAPL", "aapl": "AAPL",
    "microsoft": "MSFT", "msft": "MSFT",
    "google": "GOOGL", "alphabet": "GOOGL", "googl": "GOOGL",
    "amazon": "AMZN", "amzn": "AMZN",
    "nvidia": "NVDA", "nvda": "NVDA",
    "tesla": "TSLA", "tsla": "TSLA",
    "meta": "META", "facebook": "META",
    "netflix": "NFLX", "nflx": "NFLX",
    "exxon": "XOM", "xom": "XOM",
    "chevron": "CVX", "cvx": "CVX",
    "jpmorgan": "JPM", "jpm": "JPM",
    "goldman": "GS", "gs": "GS",
    "visa": "V",
    "bitcoin": "BTC/USD", "btc": "BTC/USD",
    "ethereum": "ETH/USDT", "eth": "ETH/USDT",
    "dogecoin": "DOGE/USD", "doge": "DOGE/USD",
    "eurusd": "EURUSD", "eur/usd": "EURUSD",
    "usdjpy": "USDJPY", "usd/jpy": "USDJPY",
    "gbpusd": "GBPUSD", "gbp/usd": "GBPUSD",
    "oil": "XOM",  # proxy via Exxon
    "gold": "GS",  # proxy
    "sp500": "AAPL",  # proxy
    "s&p": "AAPL",
}

_ASSET_CLASS_MAP = {
    "equity": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "NFLX",
               "XOM", "CVX", "JPM", "GS", "V", "BAC", "WMT", "HD", "CRM",
               "ORCL", "ABBV", "CAT", "GE", "COP", "COST", "DE", "ADBE",
               "AMD", "AVGO", "AXP", "WFC"],
    "crypto": ["BTC/USD", "ETH/USDT", "DOGE/USD", "AVAX/USD", "LINK/USD",
               "AAVE/USD", "BCH/USD"],
    "fx": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
           "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"],
}


def _resolve_symbol(text: str) -> tuple[str, str] | None:
    """Try to resolve text to (symbol, asset_class)."""
    text_lower = text.lower().strip()
    if text_lower in _EQUITY_ALIASES:
        sym = _EQUITY_ALIASES[text_lower]
        # Determine asset class
        if "/" in sym:
            return sym, "crypto"
        elif len(sym) == 6 and sym.isalpha() and sym.isupper():
            return sym, "fx"
        else:
            return sym, "equity"
    # Check if it's a raw ticker
    text_upper = text.upper().strip()
    for ac, symbols in _ASSET_CLASS_MAP.items():
        if text_upper in symbols:
            return text_upper, ac
    return None


def parse_user_prompt(prompt: str, available_assets: dict | None = None) -> dict:
    """
    Parse a natural language research question into structured parameters.

    Returns dict with:
        - target_symbol: str (e.g. 'AAPL')
        - target_asset_class: str ('equity', 'crypto', 'fx')
        - feature_symbols: list[str] (other assets to use as features)
        - trend_keywords: list[str] (Google Trends keywords to pull)
    """
    # Try OpenAI-powered smart parsing first
    if OPENAI_API_KEY:
        try:
            return _parse_with_openai(prompt, available_assets)
        except Exception as e:
            print(f"  ⚠ AI prompt parsing failed ({e}) — using rule-based parser")

    return _parse_rule_based(prompt)


def _parse_with_openai(prompt: str, available_assets: dict | None = None) -> dict:
    """Use OpenAI to intelligently parse the user's research question."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build context about available data
    asset_context = ""
    if available_assets:
        eq_syms = [a["symbol"] for a in available_assets.get("equity", [])][:30]
        crypto_syms = [a["symbol"] for a in available_assets.get("crypto", [])][:20]
        fx_syms = [a["symbol"] for a in available_assets.get("fx", [])][:10]
        trend_kws = [a["keyword"] for a in available_assets.get("trends", [])][:50]
        asset_context = f"""
Available equities: {eq_syms}
Available crypto: {crypto_syms}
Available FX: {fx_syms}
Sample trend keywords: {trend_kws}
"""

    system = """You parse research questions into structured trading parameters.
Return ONLY valid JSON with these fields:
- "target_symbol": the main asset to predict (must be an exact symbol like "AAPL", "BTC/USD", "EURUSD")
- "target_asset_class": one of "equity", "crypto", "fx"
- "feature_symbols": list of 2-5 other asset symbols that could be related
- "trend_keywords": list of 3-8 Google Trends search terms that could be leading indicators
No markdown, no explanation."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Research question: {prompt}\n{asset_context}"},
        ],
        temperature=0.3,
        max_tokens=500,
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    parsed = json.loads(text)

    # Validate required fields
    result = {
        "target_symbol": parsed.get("target_symbol", "AAPL"),
        "target_asset_class": parsed.get("target_asset_class", "equity"),
        "feature_symbols": parsed.get("feature_symbols", []),
        "trend_keywords": parsed.get("trend_keywords", []),
    }

    # Validate asset class
    if result["target_asset_class"] not in ("equity", "crypto", "fx"):
        result["target_asset_class"] = "equity"

    return result


def _parse_rule_based(prompt: str) -> dict:
    """Simple rule-based fallback parser."""
    prompt_lower = prompt.lower()
    words = prompt_lower.replace("?", "").replace(",", " ").split()

    # 1. Find target asset
    target_symbol = "AAPL"
    target_ac = "equity"
    for word in words:
        resolved = _resolve_symbol(word)
        if resolved:
            target_symbol, target_ac = resolved
            break

    # 2. Pick related feature symbols
    feature_symbols = []
    # Add a few related assets
    if target_ac == "equity":
        candidates = [s for s in _ASSET_CLASS_MAP["equity"] if s != target_symbol]
        feature_symbols = random.sample(candidates, min(3, len(candidates)))
        # Add a crypto and fx for cross-asset signals
        feature_symbols.append("BTC/USD")
        feature_symbols.append("EURUSD")
    elif target_ac == "crypto":
        feature_symbols = ["AAPL", "NVDA", "EURUSD"]
    elif target_ac == "fx":
        feature_symbols = ["AAPL", "BTC/USD", "XOM"]

    # 3. Extract trend keywords from the prompt + add defaults
    trend_keywords = []
    keyword_hints = {
        "ai": ["artificial intelligence", "ai stocks", "chatgpt"],
        "oil": ["oil price", "crude oil", "brent crude"],
        "crypto": ["bitcoin price", "crypto regulation"],
        "tech": ["artificial intelligence", "ai stocks"],
        "inflation": ["inflation rate", "consumer price index", "fed rate decision"],
        "war": ["geopolitical risk", "war impact economy"],
        "rate": ["fed rate decision", "rate hike", "rate cut"],
        "interest": ["fed rate decision", "interest rates"],
        "energy": ["oil price", "renewable energy", "oil production"],
        "gold": ["gold price"],
        "dollar": ["us dollar index", "fed rate decision"],
    }
    for word in words:
        if word in keyword_hints:
            trend_keywords.extend(keyword_hints[word])

    # Default trends if none found
    if not trend_keywords:
        trend_keywords = ["artificial intelligence", "oil price", "inflation rate"]

    # Deduplicate
    trend_keywords = list(dict.fromkeys(trend_keywords))[:8]

    return {
        "target_symbol": target_symbol,
        "target_asset_class": target_ac,
        "feature_symbols": feature_symbols,
        "trend_keywords": trend_keywords,
    }
