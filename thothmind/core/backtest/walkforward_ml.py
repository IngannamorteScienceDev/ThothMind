from __future__ import annotations

import numpy as np
import pandas as pd

from thothmind.core.backtest.metrics import compute_metrics
from thothmind.core.backtest.simulator import simulate_daily
from thothmind.core.decision.allocation import predictions_to_exposure
from thothmind.core.models.xgb_regressor import XGBConfig, XGBReturnRegressor


def _add_continuous_equity(sim_df: pd.DataFrame, initial_equity: float = 1.0) -> pd.DataFrame:
    df = sim_df.copy().sort_values("date").reset_index(drop=True)

    equity = [float(initial_equity)]
    for i in range(1, len(df)):
        equity.append(equity[-1] * (1.0 + float(df.loc[i, "pnl"])))

    df["equity"] = equity
    roll_max = df["equity"].cummax()
    df["drawdown"] = df["equity"] / roll_max - 1.0
    return df


def run_walkforward_ml_oos(
    df_feat: pd.DataFrame,
    feature_cols: list[str],
    splits: list[dict],
    model_cfg: dict,
    decision_cfg: dict,
    commission_bps: float,
    slippage_k: float,
    initial_equity: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    For each split:
      - Fit model on train rows
      - Predict on [warmup=train_end .. test_end]
      - Convert predictions -> target_exposure (0/0.5/1)
      - Simulate window and keep ONLY test days (drop warmup row)

    Returns:
      sim_oos_cont, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
    """
    df_feat = df_feat.copy().sort_values("date").reset_index(drop=True)

    xgb_cfg = XGBConfig(
        n_estimators=int(model_cfg.get("n_estimators", 600)),
        max_depth=int(model_cfg.get("max_depth", 4)),
        learning_rate=float(model_cfg.get("learning_rate", 0.03)),
        subsample=float(model_cfg.get("subsample", 0.8)),
        colsample_bytree=float(model_cfg.get("colsample_bytree", 0.8)),
        reg_lambda=float(model_cfg.get("reg_lambda", 1.0)),
        min_child_weight=float(model_cfg.get("min_child_weight", 1.0)),
        random_state=int(model_cfg.get("random_state", 42)),
    )

    thr_half = float(decision_cfg.get("thr_half", 0.0))
    thr_full = float(decision_cfg.get("thr_full", 0.001))

    all_oos_sims = []
    window_rows = []
    all_preds = []
    all_signals = []

    for w_id, sp in enumerate(splits, start=1):
        tr_s = int(sp["train_start"])
        tr_e = int(sp["train_end"])
        ts = int(sp["test_start"])
        te = int(sp["test_end"])

        warmup = tr_e  # == test_start - 1 by construction

        # --- Train ---
        train_df = df_feat.iloc[tr_s : tr_e + 1].copy()
        X_train = train_df[feature_cols]
        y_train = train_df["y"]

        model = XGBReturnRegressor(xgb_cfg)
        model.fit(X_train, y_train)

        # --- Predict for warmup + test (needed for signal[t]->position[t+1]) ---
        pred_df = df_feat.iloc[warmup : te + 1].copy().reset_index(drop=True)
        X_pred = pred_df[feature_cols]
        y_pred = model.predict(X_pred)

        pred_df["y_pred"] = y_pred
        pred_df["window_id"] = w_id

        # Convert predictions -> discrete exposures
        target_exposure = predictions_to_exposure(y_pred, thr_half=thr_half, thr_full=thr_full)

        signals_df = pred_df[["date"]].copy()
        signals_df["target_exposure"] = target_exposure
        signals_df["signal_name"] = "xgb_regressor"
        signals_df["window_id"] = w_id

        # Simulator expects date-aligned signals (date + target_exposure + signal_name)
        # It merges by date and then shifts target_exposure by 1 day internally.
        sim_window = simulate_daily(
            df_feat=pred_df,
            signals_df=signals_df.rename(columns={"window_id": "window_id_sig"}),
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            initial_equity=float(initial_equity),
        )

        # Drop warmup row -> keep only OOS test days
        sim_test = sim_window.iloc[1:].copy().reset_index(drop=True)

        # Add window metadata
        sim_test["window_id"] = w_id
        sim_test["train_start_date"] = pd.to_datetime(df_feat.iloc[tr_s]["date"])
        sim_test["train_end_date"] = pd.to_datetime(df_feat.iloc[tr_e]["date"])
        sim_test["test_start_date"] = pd.to_datetime(df_feat.iloc[ts]["date"])
        sim_test["test_end_date"] = pd.to_datetime(df_feat.iloc[te]["date"])

        # Preserve per-window equity as window_equity/window_drawdown
        sim_test = sim_test.rename(columns={"equity": "window_equity", "drawdown": "window_drawdown"})

        # Per-window metrics
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

        # Save predictions/signals for OOS test days only (drop warmup row)
        pred_oos = pred_df.iloc[1:].copy().reset_index(drop=True)
        pred_oos["window_id"] = w_id
        pred_oos = pred_oos[["date", "ticker", "y", "y_pred", "market_regime", "realized_vol", "window_id"]].copy()

        sig_oos = signals_df.iloc[1:].copy().reset_index(drop=True)
        sig_oos["window_id"] = w_id

        all_preds.append(pred_oos)
        all_signals.append(sig_oos)
        all_oos_sims.append(sim_test)

    # Concatenate all windows
    sim_oos = pd.concat(all_oos_sims, ignore_index=True)
    window_metrics_df = pd.DataFrame(window_rows)
    predictions_oos_df = pd.concat(all_preds, ignore_index=True)
    signals_oos_df = pd.concat(all_signals, ignore_index=True)

    # Continuous equity over concatenated OOS pnl
    sim_oos_cont = sim_oos.copy()
    sim_oos_cont["equity"] = np.nan
    sim_oos_cont["drawdown"] = np.nan
    sim_oos_cont = _add_continuous_equity(sim_oos_cont, initial_equity=float(initial_equity))

    run_metrics = compute_metrics(sim_oos_cont)

    return sim_oos_cont, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
