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
) -> pd.DataFrame:
    """
    Daily simulator with realistic costs:

    - Commission: turnover * (commission_bps / 10000)
    - Slippage:  turnover * ((slippage_bps + slippage_vol_k * vol_bps) / 10000)

      where vol_bps is daily volatility proxy in bps:
        vol_bps ≈ |return| * 10000  (or realized_vol if it is already daily vol in fraction)

    This prevents "percent-per-day" slippage explosions.
    """
    if df_feat is None or len(df_feat) == 0:
        return pd.DataFrame()

    df = df_feat.copy()
    df["date"] = pd.to_datetime(df["date"])

    sig = signals_df.copy()
    sig["date"] = pd.to_datetime(sig["date"])
    if "target_exposure" not in sig.columns:
        raise KeyError("signals_df must contain 'target_exposure'.")

    sig = sig[["date", "target_exposure"]].drop_duplicates("date").sort_values("date")
    df = df.sort_values("date")
    df = pd.merge(df, sig, on="date", how="left")

    df["target_exposure"] = df["target_exposure"].astype(float).ffill().fillna(0.0).clip(-1.0, 1.0)
    df["exposure"] = df["target_exposure"]

    prev_exp = df["exposure"].shift(1).fillna(0.0)
    df["turnover"] = (df["exposure"] - prev_exp).abs()

    r_col = _pick_return_column(df)
    r = df[r_col].astype(float).to_numpy()

    # Commission (bps)
    commission_rate = float(commission_bps) / 10000.0
    df["commission_cost"] = df["turnover"] * commission_rate

    # Volatility proxy in bps (daily)
    # If realized_vol exists and is fraction (e.g., 0.01 for 1%), convert to bps.
    if "realized_vol" in df.columns:
        vol = df["realized_vol"].astype(float).to_numpy()
        vol = np.where(np.isfinite(vol), vol, 0.0)
        vol = np.clip(vol, 0.0, 1.0)  # daily vol above 100% makes no sense
        vol_bps = vol * 10000.0
    else:
        vol_bps = np.abs(r) * 10000.0

    # Slippage (bps) scaled by vol_bps
    slip_bps_eff = float(slippage_bps) + float(slippage_vol_k) * (vol_bps / 10000.0)  # convert back to fraction-of-1 scale
    # But keep it in bps and cap
    slip_bps_eff = np.clip(slip_bps_eff, 0.0, 50.0)  # cap at 50 bps per turnover (very conservative)
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
