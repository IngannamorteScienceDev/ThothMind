from __future__ import annotations

import numpy as np
import pandas as pd


RETURN_COL_CANDIDATES = ["ret_1d", "y", "ret", "return", "r"]


def _pick_return_column(df: pd.DataFrame) -> str:
    for c in RETURN_COL_CANDIDATES:
        if c in df.columns:
            return c
    raise KeyError(f"No return column found. Expected one of: {RETURN_COL_CANDIDATES}")


def simulate_daily(
    df_feat: pd.DataFrame,
    signals_df: pd.DataFrame,
    commission_bps: float = 2.0,
    slippage_bps: float = 1.0,
    slippage_vol_k: float = 10.0,
    initial_equity: float = 1.0,
    execution_lag: int = 0,
) -> pd.DataFrame:
    """
    Daily simulator with realistic costs.

    execution_lag:
      - 0: execute same day (exposure_t = target_exposure_t)
      - 1: execute next day (exposure_t = target_exposure_{t-1}) to avoid lookahead
    """
    if df_feat is None or len(df_feat) == 0:
        return pd.DataFrame()

    lag = int(execution_lag)
    if lag < 0:
        raise ValueError("execution_lag must be >= 0")

    df = df_feat.copy()
    df["date"] = pd.to_datetime(df["date"])

    sig = signals_df.copy()
    sig["date"] = pd.to_datetime(sig["date"])
    if "target_exposure" not in sig.columns:
        raise KeyError("signals_df must contain 'target_exposure'.")

    sig = sig[["date", "target_exposure"]].drop_duplicates("date").sort_values("date")
    df = df.sort_values("date")
    df = pd.merge(df, sig, on="date", how="left")

    df["target_exposure"] = (
        df["target_exposure"].astype(float).ffill().fillna(0.0).clip(-1.0, 1.0)
    )

    if lag == 0:
        df["exposure"] = df["target_exposure"]
    else:
        df["exposure"] = df["target_exposure"].shift(lag).fillna(0.0).clip(-1.0, 1.0)

    prev_exp = df["exposure"].shift(1).fillna(0.0)
    df["turnover"] = (df["exposure"] - prev_exp).abs()

    r_col = _pick_return_column(df)
    r = df[r_col].astype(float).to_numpy()

    commission_rate = float(commission_bps) / 10000.0
    df["commission_cost"] = df["turnover"] * commission_rate

    if "realized_vol" in df.columns:
        vol = df["realized_vol"].astype(float).to_numpy()
        vol = np.where(np.isfinite(vol), vol, 0.0)
        vol = np.clip(vol, 0.0, 1.0)
        vol_frac = vol
    else:
        vol_frac = np.abs(r)

    slip_bps_eff = float(slippage_bps) + float(slippage_vol_k) * vol_frac
    slip_bps_eff = np.clip(slip_bps_eff, 0.0, 50.0)

    df["slippage_cost"] = df["turnover"] * (slip_bps_eff / 10000.0)
    df["total_cost"] = df["commission_cost"] + df["slippage_cost"]

    df["gross_ret"] = df["exposure"] * r
    df["net_ret"] = df["gross_ret"] - df["total_cost"]

    equity = np.empty(len(df), dtype=float)
    pnl = np.empty(len(df), dtype=float)

    eq = float(initial_equity)
    for i in range(len(df)):
        ret_i = float(df["net_ret"].iloc[i])
        pnl[i] = eq * ret_i
        eq = max(eq * (1.0 + ret_i), 1e-12)
        equity[i] = eq

    df["pnl"] = pnl
    df["equity"] = equity
    peak = df["equity"].cummax()
    df["drawdown"] = df["equity"] / peak - 1.0

    keep_optional = [
        c for c in ["ticker", "ret_1d", "y", "realized_vol", "market_regime"] if c in df.columns
    ]
    out_cols = [
        "date",
        *keep_optional,
        "target_exposure",
        "exposure",
        "turnover",
        "gross_ret",
        "commission_cost",
        "slippage_cost",
        "total_cost",
        "net_ret",
        "pnl",
        "equity",
        "drawdown",
    ]
    return df[out_cols].copy()
