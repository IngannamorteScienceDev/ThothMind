from __future__ import annotations

import pandas as pd

from thothmind.core.backtest.metrics import compute_metrics
from thothmind.core.backtest.simulator import simulate_daily


def run_walkforward_oos(
    df_feat: pd.DataFrame,
    signals_full: pd.DataFrame,
    splits: list[dict],
    commission_bps: float,
    slippage_bps: float,
    slippage_vol_k: float,
    initial_equity: float = 1.0,
    execution_lag: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Generic walk-forward runner for any precomputed signals (baselines, buy&hold).
    Costs use new schema: slippage_bps + slippage_vol_k.
    Equity is stitched window-to-window.

    execution_lag:
      - 0: execute same day (exposure_t = target_exposure_t)
      - 1: execute next day (exposure_t = target_exposure_{t-1}) to avoid lookahead

    Returns: sim_oos_df, window_metrics_df, run_metrics
    """
    df_feat = df_feat.copy().sort_values("date").reset_index(drop=True)
    df_feat["date"] = pd.to_datetime(df_feat["date"])

    sig = signals_full.copy()
    sig["date"] = pd.to_datetime(sig["date"])
    if "target_exposure" not in sig.columns:
        raise KeyError("signals_full must contain 'target_exposure'.")

    lag = int(execution_lag)
    if lag < 0:
        raise ValueError("execution_lag must be >= 0")

    equity0 = float(initial_equity)

    all_oos: list[pd.DataFrame] = []
    window_rows: list[dict] = []

    for w_id, sp in enumerate(splits, start=1):
        tr_s = int(sp["train_start"])
        tr_e = int(sp["train_end"])
        ts = int(sp["test_start"])
        te = int(sp["test_end"])

        # simulate on train_end..test_end span for correct turnover, then slice OOS
        span_df = df_feat.iloc[tr_e : te + 1].copy().reset_index(drop=True)
        span_start = span_df["date"].min()
        span_end = span_df["date"].max()

        span_sig = sig[(sig["date"] >= span_start) & (sig["date"] <= span_end)].copy()

        sim_span = simulate_daily(
            df_feat=span_df,
            signals_df=span_sig,
            commission_bps=float(commission_bps),
            slippage_bps=float(slippage_bps),
            slippage_vol_k=float(slippage_vol_k),
            initial_equity=float(equity0),
            execution_lag=lag,
        )

        test_start_date = df_feat.iloc[ts]["date"]
        test_end_date = df_feat.iloc[te]["date"]

        sim_span["date"] = pd.to_datetime(sim_span["date"])
        sim_oos = sim_span[(sim_span["date"] >= test_start_date) & (sim_span["date"] <= test_end_date)].copy()
        if sim_oos.empty:
            raise RuntimeError(f"Empty OOS slice for window {w_id}.")

        sim_oos = sim_oos.reset_index(drop=True)
        sim_oos["window_id"] = w_id
        sim_oos["train_start_date"] = df_feat.iloc[tr_s]["date"]
        sim_oos["train_end_date"] = df_feat.iloc[tr_e]["date"]
        sim_oos["test_start_date"] = test_start_date
        sim_oos["test_end_date"] = test_end_date

        equity0 = float(sim_oos["equity"].iloc[-1])

        m = compute_metrics(sim_oos)
        window_rows.append(
            {
                "window_id": w_id,
                "train_start": str(df_feat.iloc[tr_s]["date"].date()),
                "train_end": str(df_feat.iloc[tr_e]["date"].date()),
                "test_start": str(test_start_date.date()),
                "test_end": str(test_end_date.date()),
                "n_train": int(tr_e - tr_s + 1),
                "n_test": int(te - ts + 1),
                "execution_lag": int(lag),
                **m,
            }
        )

        all_oos.append(sim_oos)

    sim_oos_df = pd.concat(all_oos, ignore_index=True)
    window_metrics_df = pd.DataFrame(window_rows)
    run_metrics = compute_metrics(sim_oos_df)

    return sim_oos_df, window_metrics_df, run_metrics
