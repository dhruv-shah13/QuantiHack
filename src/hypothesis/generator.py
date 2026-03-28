"""
EvoAlpha — Hypothesis Generator (OpenAI GPT-4o Agent)
Takes a user prompt + available features → generates an initial population of strategies.
Falls back to random generation if OpenAI is unavailable.
"""
import json
import random
from src.strategy.code_generator import Strategy, _make_id, random_population
from config.settings import (
    OPENAI_API_KEY, TRANSFORMS, WINDOWS, LAGS, SIGNAL_TYPES
)


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
    target: str = "oil_price",
    n: int = 20,
) -> list[Strategy]:
    """
    Use Gemini to generate an initial population of strategies from a user prompt.
    Falls back to random generation if Gemini is unavailable or fails.
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


def parse_user_prompt(prompt: str, available_features: list[str]) -> dict:
    """
    Simple parser to extract target and feature hints from natural language.
    Returns dict with 'target_hint' and 'feature_hints'.
    """
    prompt_lower = prompt.lower()

    # Common target keywords
    target_keywords = {
        "oil": "oil_price",
        "gas": "gas_price",
        "shipping": "shipping_index",
    }

    target_hint = "oil_price"  # default
    for keyword, target_name in target_keywords.items():
        if keyword in prompt_lower and target_name in available_features + ["oil_price", "gas_price"]:
            target_hint = target_name
            break

    # Feature hints — any available feature mentioned
    feature_hints = [f for f in available_features if f.replace("_", " ") in prompt_lower or f in prompt_lower]

    return {
        "target_hint": target_hint,
        "feature_hints": feature_hints if feature_hints else available_features,
    }
