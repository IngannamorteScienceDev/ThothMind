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
        equity.append(equity[-1] * (1.0 + float(df.loc[i, "net_ret"])))

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
    slippage_bps: float = 1.0,
    slippage_vol_k: float = 10.0,
    slippage_k: float | None = None,
    initial_equity: float = 1.0,
    execution_lag: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Walk-forward ML OOS evaluation.

    Supports both:
      - new cost schema: slippage_bps + slippage_vol_k
      - legacy schema: slippage_k (mapped to slippage_vol_k)
    """
    df_feat = df_feat.copy().sort_values("date").reset_index(drop=True)
    df_feat["date"] = pd.to_datetime(df_feat["date"])

    if slippage_k is not None:
        slippage_vol_k = float(slippage_k)

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
    low_exposure = float(decision_cfg.get("low_exposure", 0.0))
    mid_exposure = float(decision_cfg.get("mid_exposure", 0.5))
    high_exposure = float(decision_cfg.get("high_exposure", 1.0))
    min_hold_days = int(decision_cfg.get("min_hold_days", 0))

    all_oos_sims: list[pd.DataFrame] = []
    window_rows: list[dict] = []
    all_preds: list[pd.DataFrame] = []
    all_signals: list[pd.DataFrame] = []

    equity0 = float(initial_equity)
    lag = int(execution_lag)
    if lag < 0:
        raise ValueError("execution_lag must be >= 0")

    for w_id, sp in enumerate(splits, start=1):
        tr_s = int(sp["train_start"])
        tr_e = int(sp["train_end"])
        ts = int(sp["test_start"])
        te = int(sp["test_end"])

        train_df = df_feat.iloc[tr_s : tr_e + 1].copy()
        model = XGBReturnRegressor(xgb_cfg)
        model.fit(train_df[feature_cols], train_df["y"])

        pred_span = df_feat.iloc[tr_e : te + 1].copy().reset_index(drop=True)
        y_pred = model.predict(pred_span[feature_cols])

        pred_span["y_pred"] = y_pred
        pred_span["window_id"] = w_id

        target_exposure = predictions_to_exposure(
            y_pred,
            thr_half=thr_half,
            thr_full=thr_full,
            low_exposure=low_exposure,
            mid_exposure=mid_exposure,
            high_exposure=high_exposure,
            min_hold_days=min_hold_days,
        )

        signals_span = pred_span[["date"]].copy()
        signals_span["target_exposure"] = target_exposure
        signals_span["signal_name"] = "xgb_regressor"
        signals_span["window_id"] = w_id

        sim_span = simulate_daily(
            df_feat=pred_span,
            signals_df=signals_span,
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

        pred_span["date"] = pd.to_datetime(pred_span["date"])
        pred_oos = pred_span[(pred_span["date"] >= test_start_date) & (pred_span["date"] <= test_end_date)].copy()
        pred_keep = [
            c for c in ["date", "ticker", "y", "y_pred", "market_regime", "realized_vol", "window_id"]
            if c in pred_oos.columns
        ]
        pred_oos = pred_oos[pred_keep].copy()

        sig_oos = signals_span.copy()
        sig_oos["date"] = pd.to_datetime(sig_oos["date"])
        sig_oos = sig_oos[(sig_oos["date"] >= test_start_date) & (sig_oos["date"] <= test_end_date)].copy().reset_index(drop=True)

        all_preds.append(pred_oos)
        all_signals.append(sig_oos)
        all_oos_sims.append(sim_oos)

    sim_oos_df = pd.concat(all_oos_sims, ignore_index=True)
    window_metrics_df = pd.DataFrame(window_rows)
    predictions_oos_df = pd.concat(all_preds, ignore_index=True) if all_preds else pd.DataFrame()
    signals_oos_df = pd.concat(all_signals, ignore_index=True) if all_signals else pd.DataFrame()

    run_metrics = compute_metrics(sim_oos_df)
    run_metrics["decision"] = {
        "thr_half": float(thr_half),
        "thr_full": float(thr_full),
        "low_exposure": float(low_exposure),
        "mid_exposure": float(mid_exposure),
        "high_exposure": float(high_exposure),
        "min_hold_days": int(min_hold_days),
    }

    return sim_oos_df, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
