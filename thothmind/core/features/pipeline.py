from __future__ import annotations

import numpy as np
import pandas as pd


def build_features(
    df: pd.DataFrame,
    horizon: int = 1,
    sma_windows: list[int] | None = None,
    vol_windows: list[int] | None = None,
    lags: list[int] | None = None,
) -> pd.DataFrame:
    """
    Build daily features and labels.
    Input df must have: date, close, volume, ticker (plus OHLC).
    Output: df_feat with ret_1d, y (forward_return_h), and feature columns.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    sma_windows = sma_windows or [5, 20, 50, 200]
    vol_windows = vol_windows or [10, 20, 60]
    lags = lags or [1, 5, 20]

    # === Basic returns ===
    df["ret_1d"] = df["close"].pct_change(1)

    # === Trend features (SMA ratios) ===
    for w in sma_windows:
        df[f"sma_ratio_{w}"] = df["close"].rolling(w).mean() / df["close"]

    # === Volatility features ===
    for w in vol_windows:
        df[f"vol_{w}"] = df["ret_1d"].rolling(w).std()

    # === Lagged returns ===
    for l in lags:
        df[f"lag_ret_{l}"] = df["ret_1d"].shift(l)

    # === Volume features (simple, but useful) ===
    df["log_volume"] = np.log1p(df["volume"])
    df["vol_z_20"] = (df["log_volume"] - df["log_volume"].rolling(20).mean()) / df["log_volume"].rolling(20).std()

    # === Label ===
    df["forward_return_h"] = df["close"].shift(-horizon) / df["close"] - 1.0
    df["y"] = df["forward_return_h"]
    df["horizon"] = int(horizon)

    # Clean
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna().reset_index(drop=True)

    return df


def infer_feature_columns(df_feat: pd.DataFrame) -> list[str]:
    """
    Return feature columns (exclude identifiers and targets).
    """
    exclude = {
        "date", "ticker",
        "open", "high", "low", "close", "volume",
        "ret_1d",
        "forward_return_h", "y", "horizon",
        "realized_vol", "trend_state", "vol_state", "market_regime",
        "trend_regime", "vol_regime",  # legacy names (if present)
    }
    return [c for c in df_feat.columns if c not in exclude]
