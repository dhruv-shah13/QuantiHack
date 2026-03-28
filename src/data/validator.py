"""
EvoAlpha — Data Validator
Validates that loaded data is clean and usable by the evolution engine.
"""
import pandas as pd


def validate_dataset(df: pd.DataFrame, target: str = "oil_price") -> dict:
    """
    Run basic validation checks on the dataset.
    Returns a dict with status and any issues found.
    """
    issues = []

    if df.empty:
        issues.append("Dataset is empty")

    if target not in df.columns:
        issues.append(f"Target column '{target}' not found. Available: {list(df.columns)}")

    if df.isnull().any().any():
        null_cols = df.columns[df.isnull().any()].tolist()
        issues.append(f"Null values found in: {null_cols}")

    if not isinstance(df.index, pd.DatetimeIndex):
        issues.append("Index is not DatetimeIndex — timestamps may not be parsed")

    feature_cols = [c for c in df.columns if c != target]
    if len(feature_cols) == 0:
        issues.append("No feature columns found (only target)")

    return {
        "valid": len(issues) == 0,
        "rows": len(df),
        "features": [c for c in df.columns if c != target],
        "target": target,
        "date_range": f"{df.index.min()} → {df.index.max()}" if not df.empty else "N/A",
        "issues": issues,
    }
