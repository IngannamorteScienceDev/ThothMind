from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(sim_df: pd.DataFrame, annualization: int = 252) -> dict:
    """
    Compute core strategy metrics from sim_df (daily pnl series).
    """
    pnl = sim_df["pnl"].astype(float).to_numpy()
    pnl = pnl[~np.isnan(pnl)]

    equity_end = float(sim_df["equity"].iloc[-1])
    total_return = equity_end - 1.0

    # Sharpe on daily pnl
    mean = float(np.mean(pnl)) if len(pnl) else 0.0
    std = float(np.std(pnl, ddof=1)) if len(pnl) > 1 else 0.0
    sharpe = 0.0 if std == 0.0 else (mean / std) * np.sqrt(annualization)

    max_dd = float(sim_df["drawdown"].min())

    avg_turnover = float(sim_df["turnover"].mean())
    total_cost = float(sim_df["total_cost"].sum())

    return {
        "rows": int(len(sim_df)),
        "total_return": float(total_return),
        "equity_end": float(equity_end),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "avg_turnover": float(avg_turnover),
        "total_cost": float(total_cost),
    }
