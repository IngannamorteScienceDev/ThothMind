from __future__ import annotations

import numpy as np
import pandas as pd


def _ensure_drawdown(sim_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure drawdown column exists based on equity curve.
    drawdown = equity / cummax(equity) - 1
    """
    df = sim_df.copy()
    if "drawdown" not in df.columns:
        if "equity" not in df.columns:
            raise KeyError("compute_metrics requires 'equity' column (or precomputed 'drawdown').")
        eq = df["equity"].astype(float)
        peak = eq.cummax()
        df["drawdown"] = eq / peak - 1.0
    return df


def compute_metrics(sim_df: pd.DataFrame) -> dict:
    """
    Compute standard backtest metrics from a simulation dataframe.

    Expected minimal columns:
      - equity (required)
      - net_ret OR pnl (optional, used to infer returns)

    We compute drawdown internally if missing.
    """
    if sim_df is None or len(sim_df) < 5:
        return {
            "n_days": int(0),
            "total_return": float(0.0),
            "cagr": float(0.0),
            "vol_annual": float(0.0),
            "sharpe": float(0.0),
            "max_drawdown": float(0.0),
        }

    df = sim_df.copy()
    df = _ensure_drawdown(df)

    # Equity
    eq = df["equity"].astype(float).to_numpy()
    n = len(eq)

    # Daily returns: prefer net_ret if present, else infer from equity
    if "net_ret" in df.columns:
        r = df["net_ret"].astype(float).to_numpy()
    else:
        # infer from equity: r_t = eq_t/eq_{t-1} - 1
        r = np.empty(n, dtype=float)
        r[0] = 0.0
        r[1:] = eq[1:] / np.maximum(eq[:-1], 1e-12) - 1.0

    # Total return
    total_return = float(eq[-1] / max(eq[0], 1e-12) - 1.0)

    # CAGR (assume 252 trading days/year)
    years = n / 252.0
    cagr = float((eq[-1] / max(eq[0], 1e-12)) ** (1.0 / max(years, 1e-9)) - 1.0)

    # Annualized vol
    vol_annual = float(np.std(r[1:], ddof=1) * np.sqrt(252)) if n > 2 else 0.0

    # Sharpe (risk-free ignored; consistent across baselines)
    mean_daily = float(np.mean(r[1:])) if n > 1 else 0.0
    std_daily = float(np.std(r[1:], ddof=1)) if n > 2 else 0.0
    sharpe = float((mean_daily / std_daily) * np.sqrt(252)) if std_daily > 0 else 0.0

    # Max drawdown
    max_dd = float(df["drawdown"].min())

    return {
        "n_days": int(n),
        "total_return": total_return,
        "cagr": cagr,
        "vol_annual": vol_annual,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
    }
