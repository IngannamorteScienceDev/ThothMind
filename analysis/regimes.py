import pandas as pd
import numpy as np


def compute_realized_volatility(df: pd.DataFrame, window: int = 20):
    """
    Annualized realized volatility.
    """
    returns = df["Close"].pct_change()
    vol = returns.rolling(window).std() * np.sqrt(252)
    return vol


def label_volatility_regime(vol_series: pd.Series):
    """
    Low / High volatility based on median split.
    """
    threshold = vol_series.median()
    return pd.Series(
        np.where(vol_series > threshold, "HighVol", "LowVol"),
        index=vol_series.index
    )


def label_trend_regime(df: pd.DataFrame, window: int = 200):
    """
    Bull / Bear regime using long-term moving average.
    """
    sma = df["Close"].rolling(window).mean()
    return pd.Series(
        np.where(df["Close"] > sma, "Bull", "Bear"),
        index=df.index
    )


def assign_market_regime(df: pd.DataFrame):
    """
    Assign combined market regime.
    """
    df = df.copy()

    df["realized_vol"] = compute_realized_volatility(df)
    df["vol_regime"] = label_volatility_regime(df["realized_vol"])
    df["trend_regime"] = label_trend_regime(df)

    df["market_regime"] = (
        df["trend_regime"] + "-" + df["vol_regime"]
    )

    return df
