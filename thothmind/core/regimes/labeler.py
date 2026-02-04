from __future__ import annotations

import pandas as pd

from analysis.regimes import assign_market_regime_full


def add_regimes(
    df_feat: pd.DataFrame,
    vol_window: int = 20,
    vol_median_window: int = 252,
    trend_sma_window: int = 200,
) -> pd.DataFrame:
    """
    Add market regimes using legacy regime labeling, then normalize:
    trend_state: bull/bear
    vol_state: high_vol/low_vol
    market_regime: bull_high_vol etc
    """
    df = df_feat.copy()

    # Legacy function expects Date + Close
    df_legacy = df.rename(columns={"date": "Date", "close": "Close"}).copy()

    df_legacy = assign_market_regime_full(
        df_legacy,
        vol_window=vol_window,
        vol_median_window=vol_median_window,
        trend_sma_window=trend_sma_window,
    )

    # Back to standard column names
    df_out = df_legacy.rename(columns={"Date": "date", "Close": "close"}).copy()

    # Normalize regime labels
    # legacy: trend_regime = Bull/Bear, vol_regime = HighVol/LowVol, market_regime = "Bull-HighVol"
    if "trend_regime" in df_out.columns:
        df_out["trend_state"] = df_out["trend_regime"].map({"Bull": "bull", "Bear": "bear"})
    if "vol_regime" in df_out.columns:
        df_out["vol_state"] = df_out["vol_regime"].map({"HighVol": "high_vol", "LowVol": "low_vol"})

    if "trend_state" in df_out.columns and "vol_state" in df_out.columns:
        df_out["market_regime"] = df_out["trend_state"] + "_" + df_out["vol_state"]

    return df_out
