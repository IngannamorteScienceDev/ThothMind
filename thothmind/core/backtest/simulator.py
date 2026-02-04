from __future__ import annotations

import numpy as np
import pandas as pd

from thothmind.core.execution.costs import compute_costs
from thothmind.core.execution.position import PositionManager


def simulate_daily(
    df_feat: pd.DataFrame,
    signals_df: pd.DataFrame,
    commission_bps: float = 2.0,
    slippage_k: float = 0.15,
    initial_equity: float = 1.0,
) -> pd.DataFrame:
    """
    Event-driven daily simulation with strict anti-lookahead:
    - signal[t] decides target_exposure[t]
    - position is applied at t+1:
        position[t] = target_exposure[t-1]

    pnl[t] = position[t-1] * ret_1d[t] - cost[t]
    (cost[t] is paid when changing position at t, i.e. turnover[t])
    """
    df = df_feat.copy().sort_values("date").reset_index(drop=True)

    # Merge signals (computed on same dates as df_feat)
    s = signals_df[["date", "target_exposure", "signal_name"]].copy()
    s["date"] = pd.to_datetime(s["date"])
    df = df.merge(s, on="date", how="left")

    if df["target_exposure"].isna().any():
        # For early rows where SMA can't be computed, default to 0 exposure
        df["target_exposure"] = df["target_exposure"].fillna(0.0)
    df["signal_name"] = df["signal_name"].fillna("baseline")

    # Anti-lookahead: apply yesterday's target as today's position
    df["target_exposure_shifted"] = df["target_exposure"].shift(1).fillna(0.0)

    pm = PositionManager()

    positions = []
    turnovers = []
    commission_costs = []
    slippage_costs = []
    total_costs = []

    prev_pos = 0.0
    for i in range(len(df)):
        tgt = float(df.loc[i, "target_exposure_shifted"])
        step = pm.step(prev_position=prev_pos, target_exposure=tgt)
        pos = step["position"]
        tnover = step["turnover"]

        rv = float(df.loc[i, "realized_vol"]) if "realized_vol" in df.columns else float(df.loc[i, "ret_1d"])
        if np.isnan(rv):
            rv = 0.0

        cost = compute_costs(
            turnover=tnover,
            realized_vol=rv,
            commission_bps=commission_bps,
            slippage_k=slippage_k,
        )

        positions.append(pos)
        turnovers.append(tnover)
        commission_costs.append(cost["commission_cost"])
        slippage_costs.append(cost["slippage_cost"])
        total_costs.append(cost["total_cost"])

        prev_pos = pos

    df["position"] = positions
    df["turnover"] = turnovers
    df["commission_cost"] = commission_costs
    df["slippage_cost"] = slippage_costs
    df["total_cost"] = total_costs

    # pnl uses previous day's position (standard: held through day)
    df["position_prev"] = df["position"].shift(1).fillna(0.0)
    df["pnl"] = df["position_prev"] * df["ret_1d"] - df["total_cost"]

    # Equity curve
    equity = [float(initial_equity)]
    for i in range(1, len(df)):
        equity.append(equity[-1] * (1.0 + float(df.loc[i, "pnl"])))
    df["equity"] = equity

    # Drawdown
    roll_max = df["equity"].cummax()
    df["drawdown"] = df["equity"] / roll_max - 1.0

    # Keep important columns up front (but preserve others too)
    front = [
        "date", "ticker", "close", "ret_1d",
        "signal_name", "target_exposure", "position", "turnover",
        "commission_cost", "slippage_cost", "total_cost",
        "pnl", "equity", "drawdown",
    ]
    # Add regime columns if present
    for c in ["trend_state", "vol_state", "market_regime", "realized_vol"]:
        if c in df.columns:
            front.append(c)

    cols = front + [c for c in df.columns if c not in front]
    df = df[cols]

    return df
