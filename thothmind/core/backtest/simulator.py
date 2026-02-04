from __future__ import annotations

import numpy as np
import pandas as pd


def _pick_return_column(df: pd.DataFrame) -> str:
    """
    Pick a reasonable realized return column for simulation.
    Priority: 'y' (common in this project) -> 'ret' -> 'return' -> 'r'
    """
    for c in ["y", "ret", "return", "r"]:
        if c in df.columns:
            return c
    raise KeyError("No return column found. Expected one of: y, ret, return, r")


def simulate_daily(
    df_feat: pd.DataFrame,
    signals_df: pd.DataFrame,
    commission_bps: float = 2.0,
    slippage_k: float = 0.15,
    initial_equity: float = 1.0,
) -> pd.DataFrame:
    """
    Daily simulator with exposure in [0..1] (or [-1..1] if you ever add shorts).

    Key principles (professional):
    - Commission is charged on TURNOVER (change in exposure), not every day.
    - commission_bps is basis points, so rate = bps / 10000.
    - Slippage is also charged on turnover and scaled by volatility proxy.

    Output columns (stable contract):
    date, target_exposure, exposure, turnover,
    gross_ret, commission_cost, slippage_cost, total_cost, net_ret,
    pnl, equity
    """
    if df_feat is None or len(df_feat) == 0:
        return pd.DataFrame()

    df = df_feat.copy()

    # Ensure dates comparable
    df["date"] = pd.to_datetime(df["date"])
    sig = signals_df.copy()
    sig["date"] = pd.to_datetime(sig["date"])

    if "target_exposure" not in sig.columns:
        raise KeyError("signals_df must contain 'target_exposure' column.")

    # Merge target_exposure onto df
    sig = sig[["date", "target_exposure"]].drop_duplicates("date").sort_values("date")
    df = df.sort_values("date")
    df = pd.merge(df, sig, on="date", how="left")

    # Fill exposure: if signal missing -> keep previous, start from 0
    df["target_exposure"] = df["target_exposure"].astype(float)
    df["target_exposure"] = df["target_exposure"].ffill().fillna(0.0)

    # Clamp (safety)
    df["target_exposure"] = df["target_exposure"].clip(-1.0, 1.0)

    # Exposure used for return on the same row.
    # (If later you want strict t->t+1 execution, shift here by 1)
    df["exposure"] = df["target_exposure"]

    prev_exp = df["exposure"].shift(1).fillna(0.0)
    df["turnover"] = (df["exposure"] - prev_exp).abs()

    # Realized return column
    r_col = _pick_return_column(df)
    r = df[r_col].astype(float).to_numpy()

    # Commission in bps => fraction of equity
    commission_rate = float(commission_bps) / 10000.0
    df["commission_cost"] = df["turnover"] * commission_rate

    # Slippage: turnover * vol_proxy * k
    if "realized_vol" in df.columns:
        vol = df["realized_vol"].astype(float).to_numpy()
        vol = np.where(np.isfinite(vol), vol, 0.0)
        vol_proxy = np.clip(vol, 0.0, 10.0)  # hard safety cap
    else:
        # fallback proxy if vol feature missing
        vol_proxy = np.abs(r)

    df["slippage_cost"] = df["turnover"] * float(slippage_k) * vol_proxy

    df["total_cost"] = df["commission_cost"] + df["slippage_cost"]

    # Gross return from exposure
    df["gross_ret"] = df["exposure"] * r

    # Net return subtracting costs
    df["net_ret"] = df["gross_ret"] - df["total_cost"]

    # Equity curve
    equity = np.empty(len(df), dtype=float)
    pnl = np.empty(len(df), dtype=float)

    eq = float(initial_equity)
    for i in range(len(df)):
        ret_i = float(df["net_ret"].iloc[i])
        # protect against blowing below zero in log-space
        eq_next = eq * (1.0 + ret_i)
        pnl[i] = eq * ret_i
        eq = max(eq_next, 1e-12)  # keep strictly positive
        equity[i] = eq

    df["pnl"] = pnl
    df["equity"] = equity

    # Return stable minimal set + keep extra columns if needed elsewhere
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
    # keep ticker if exists (useful)
    if "ticker" in df.columns:
        out_cols.insert(1, "ticker")

    return df[out_cols].copy()
