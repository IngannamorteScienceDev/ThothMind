from __future__ import annotations

import numpy as np
import pandas as pd

from thothmind.core.backtest.metrics import compute_metrics
from thothmind.core.backtest.simulator import simulate_daily


def _add_continuous_equity(sim_df: pd.DataFrame, initial_equity: float = 1.0) -> pd.DataFrame:
    """
    Recompute continuous equity/drawdown from pnl (concatenated OOS series).
    """
    df = sim_df.copy().sort_values("date").reset_index(drop=True)

    equity = [float(initial_equity)]
    for i in range(1, len(df)):
        equity.append(equity[-1] * (1.0 + float(df.loc[i, "pnl"])))

    df["equity"] = equity
    roll_max = df["equity"].cummax()
    df["drawdown"] = df["equity"] / roll_max - 1.0
    return df


def run_walkforward_oos(
    df_feat: pd.DataFrame,
    signals_full: pd.DataFrame,
    splits: list[dict],
    commission_bps: float,
    slippage_k: float,
    initial_equity: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Walk-forward simulation:
    - For each split, simulate ONLY on (warmup day + test window).
    - warmup day = test_start - 1, to ensure anti-lookahead correctness:
        signal[t] -> position[t+1]
      Costs for entering the first OOS position land on the first OOS day.

    Returns:
      - sim_oos_df: concatenated OOS sim rows for ALL windows (only test days)
      - window_metrics_df: metrics per window
      - run_metrics: metrics on concatenated OOS series
    """
    if len(df_feat) != len(signals_full):
        raise ValueError("df_feat and signals_full must have the same length.")

    all_oos_rows = []
    window_rows = []

    for w_id, sp in enumerate(splits, start=1):
        ts = int(sp["test_start"])
        te = int(sp["test_end"])
        tr_s = int(sp["train_start"])
        tr_e = int(sp["train_end"])

        warmup = ts - 1
        if warmup < 0:
            # If test starts at 0 (shouldn't), no warmup
            warmup = ts

        df_window = df_feat.iloc[warmup : te + 1].copy().reset_index(drop=True)
        sig_window = signals_full.iloc[warmup : te + 1].copy().reset_index(drop=True)

        sim_window = simulate_daily(
            df_feat=df_window,
            signals_df=sig_window,
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            initial_equity=float(initial_equity),
        )

        # Drop warmup row, keep only OOS test days
        sim_test = sim_window.iloc[1:].copy().reset_index(drop=True)

        # Add window identifiers
        sim_test["window_id"] = w_id
        sim_test["train_start_date"] = pd.to_datetime(df_feat.iloc[tr_s]["date"])
        sim_test["train_end_date"] = pd.to_datetime(df_feat.iloc[tr_e]["date"])
        sim_test["test_start_date"] = pd.to_datetime(df_feat.iloc[ts]["date"])
        sim_test["test_end_date"] = pd.to_datetime(df_feat.iloc[te]["date"])

        # Preserve per-window equity, but rename it to avoid confusion
        sim_test = sim_test.rename(columns={"equity": "window_equity", "drawdown": "window_drawdown"})

        # Compute per-window metrics (based on window-equity)
        m = compute_metrics(sim_test.rename(columns={"window_equity": "equity", "window_drawdown": "drawdown"}))

        window_rows.append(
            {
                "window_id": w_id,
                "train_start": str(df_feat.iloc[tr_s]["date"]),
                "train_end": str(df_feat.iloc[tr_e]["date"]),
                "test_start": str(df_feat.iloc[ts]["date"]),
                "test_end": str(df_feat.iloc[te]["date"]),
                "n_train": int(tr_e - tr_s + 1),
                "n_test": int(te - ts + 1),
                **m,
            }
        )

        all_oos_rows.append(sim_test)

    sim_oos = pd.concat(all_oos_rows, ignore_index=True)

    # Build continuous equity/drawdown over concatenated OOS pnl
    # Start from 1.0, chain all OOS daily pnl
    sim_oos_cont = sim_oos.copy()
    sim_oos_cont["equity"] = np.nan
    sim_oos_cont["drawdown"] = np.nan

    sim_oos_cont = _add_continuous_equity(sim_oos_cont, initial_equity=float(initial_equity))

    # Run-level metrics on continuous equity
    run_metrics = compute_metrics(sim_oos_cont)

    window_metrics_df = pd.DataFrame(window_rows)

    return sim_oos_cont, window_metrics_df, run_metrics
