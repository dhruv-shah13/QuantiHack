"""
EvoAlpha — Time Alignment
Aligns multiple datasets to a common daily frequency.
"""
import pandas as pd


def align_to_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample to daily frequency, forward-fill, drop leading NaNs.
    """
    df = df.resample("D").last()
    df = df.ffill().dropna()
    return df


def merge_datasets(*dataframes: pd.DataFrame) -> pd.DataFrame:
    """
    Merge multiple DataFrames on their DatetimeIndex (inner join).
    Each should already be indexed by timestamp.
    """
    if len(dataframes) == 0:
        return pd.DataFrame()
    
    result = dataframes[0]
    for df in dataframes[1:]:
        result = result.join(df, how="inner")
    
    return result.dropna()
