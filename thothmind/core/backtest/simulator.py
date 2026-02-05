from __future__ import annotations

import numpy as np
import pandas as pd


def _pick_return_column(df: pd.DataFrame) -> str:
    for c in ["y", "ret", "return", "r"]:
        if c in df.columns:
            return c
    raise KeyError("No return column found. Expected one of: y, ret, return, r")


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
    Daily simulator with realistic costs:

    - Commission: turnover * (commission_bps / 10000)
    - Slippage:  turnover * ((slippage_bps + slippage_vol_k * vol_frac) / 10000)

      where vol_frac is daily volatility proxy in fraction:
        vol_frac ≈ realized_vol (if provided, fraction) OR |return| (fraction)

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

    # Target exposure is the "desired" exposure for that date (signal-time series)
    df["target_exposure"] = (
        df["target_exposure"].astype(float).ffill().fillna(0.0).clip(-1.0, 1.0)
    )

    # Executed exposure: apply lag to avoid lookahead (signal at t -> execution at t+lag)
    if lag == 0:
        df["exposure"] = df["target_exposure"]
    else:
        df["exposure"] = df["target_exposure"].shift(lag).fillna(0.0).clip(-1.0, 1.0)

    prev_exp = df["exposure"].shift(1).fillna(0.0)
    df["turnover"] = (df["exposure"] - prev_exp).abs()

    r_col = _pick_return_column(df)
    r = df[r_col].astype(float).to_numpy()

    # Commission (bps)
    commission_rate = float(commission_bps) / 10000.0
    df["commission_cost"] = df["turnover"] * commission_rate

    # Volatility proxy (fraction)
    if "realized_vol" in df.columns:
        vol = df["realized_vol"].astype(float).to_numpy()
        vol = np.where(np.isfinite(vol), vol, 0.0)
        vol = np.clip(vol, 0.0, 1.0)  # daily vol above 100% makes no sense
        vol_frac = vol
    else:
        vol_frac = np.abs(r)

    # Slippage (bps) scaled by volatility fraction
    slip_bps_eff = float(slippage_bps) + float(slippage_vol_k) * vol_frac

    # Cap slippage in bps per turnover
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

    out_cols = [
        "date",
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
    ]
    if "ticker" in df.columns:
        out_cols.insert(1, "ticker")

    return df[out_cols].copy()
