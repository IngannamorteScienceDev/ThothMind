import pandas as pd
import numpy as np


def compute_realized_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    """
    Annualized realized volatility based on rolling std of daily returns.
    Uses only past data via rolling().
    """
    returns = close.pct_change()
    vol = returns.rolling(window=window, min_periods=window).std() * np.sqrt(252)
    return vol


def label_volatility_regime(vol: pd.Series, window: int = 252) -> pd.Series:
    """
    Label volatility regime using a rolling median (no leakage).
    - HighVol if realized_vol > rolling_median(realized_vol)
    - LowVol otherwise
    """
    med = vol.rolling(window=window, min_periods=window).median()
    out = pd.Series(np.where(vol > med, "HighVol", "LowVol"), index=vol.index)
    out[med.isna()] = np.nan  # not enough history to define regime
    return out


def label_trend_regime(close: pd.Series, sma_window: int = 200) -> pd.Series:
    """
    Label trend regime using SMA (no leakage).
    - Bull if Close > SMA
    - Bear otherwise
    """
    sma = close.rolling(window=sma_window, min_periods=sma_window).mean()
    out = pd.Series(np.where(close > sma, "Bull", "Bear"), index=close.index)
    out[sma.isna()] = np.nan
    return out


def assign_market_regime_full(
    df: pd.DataFrame,
    vol_window: int = 20,
    vol_median_window: int = 252,
    trend_sma_window: int = 200
) -> pd.DataFrame:
    """
    Assign market regime labels for the FULL dataframe, then you can slice windows safely.
    This avoids within-window future leakage.
    """
    df = df.copy()
    df = df.sort_values("Date").reset_index(drop=True)

    df["realized_vol"] = compute_realized_volatility(df["Close"], window=vol_window)
    df["vol_regime"] = label_volatility_regime(df["realized_vol"], window=vol_median_window)
    df["trend_regime"] = label_trend_regime(df["Close"], sma_window=trend_sma_window)

    df["market_regime"] = df["trend_regime"].astype(str) + "-" + df["vol_regime"].astype(str)

    # Drop early rows where regime is undefined (not enough rolling history)
    df = df.dropna(subset=["market_regime"]).reset_index(drop=True)
    return df
