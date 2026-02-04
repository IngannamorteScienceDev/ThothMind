from __future__ import annotations

import numpy as np
import pandas as pd

from thothmind.core.backtest.metrics import compute_metrics
from thothmind.core.backtest.simulator import simulate_daily
from thothmind.core.decision.allocation import conformal_to_exposure
from thothmind.core.models.xgb_regressor import XGBConfig, XGBReturnRegressor
from thothmind.core.models.conformal import conformal_qhat, conformal_interval


def run_walkforward_ml_conformal_oos(
    df_feat: pd.DataFrame,
    feature_cols: list[str],
    splits: list[dict],
    model_cfg: dict,
    conformal_cfg: dict,
    commission_bps: float,
    slippage_k: float,
    initial_equity: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Walk-forward ML with split conformal intervals.
    IMPORTANT: equity is stitched window-to-window using simulator output (no manual equity rebuild).

    Returns:
      sim_oos_df, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
    """
    df_feat = df_feat.copy().sort_values("date").reset_index(drop=True)

    alpha = float(conformal_cfg.get("alpha", 0.10))
    calib_size = int(conformal_cfg.get("calib_size", 252))
    min_calib = int(conformal_cfg.get("min_calib", 126))

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

    all_oos_sims: list[pd.DataFrame] = []
    window_rows: list[dict] = []
    all_preds: list[pd.DataFrame] = []
    all_signals: list[pd.DataFrame] = []

    # The key: carry equity forward window-to-window
    equity0 = float(initial_equity)

    for w_id, sp in enumerate(splits, start=1):
        tr_s = int(sp["train_start"])
        tr_e = int(sp["train_end"])
        ts = int(sp["test_start"])
        te = int(sp["test_end"])

        warmup_start = tr_e  # one day before test start (as in previous design)

        train_df = df_feat.iloc[tr_s : tr_e + 1].copy()
        n_train = len(train_df)

        use_calib = min(calib_size, n_train)
        if use_calib < min_calib:
            use_calib = max(min_calib, n_train // 2)

        calib_df = train_df.iloc[-use_calib:].copy()
        fit_df = train_df.iloc[: n_train - use_calib].copy()

        if len(fit_df) < 50:
            fit_df = train_df.iloc[: max(0, n_train - min_calib)].copy()
            calib_df = train_df.iloc[-min_calib:].copy()

        # Fit model
        model = XGBReturnRegressor(xgb_cfg)
        model.fit(fit_df[feature_cols], fit_df["y"])

        # Calibrate conformal
        yhat_cal = model.predict(calib_df[feature_cols])
        abs_res = np.abs(calib_df["y"].to_numpy(dtype=float) - yhat_cal)
        qhat = conformal_qhat(abs_res, alpha=alpha)

        # Predict for warmup+test segment
        pred_df = df_feat.iloc[warmup_start : te + 1].copy().reset_index(drop=True)
        y_pred = model.predict(pred_df[feature_cols])

        y_lo, y_hi = conformal_interval(y_pred, qhat)
        exp = conformal_to_exposure(y_pred=y_pred, y_lo=y_lo, y_hi=y_hi)

        cov = int((1 - alpha) * 100)

        pred_df["y_pred"] = y_pred
        pred_df[f"y_lo_{cov}"] = y_lo
        pred_df[f"y_hi_{cov}"] = y_hi
        pred_df[f"width_{cov}"] = (y_hi - y_lo)
        pred_df["qhat"] = float(qhat)
        pred_df["window_id"] = w_id

        signals_df = pred_df[["date"]].copy()
        signals_df["target_exposure"] = exp
        signals_df["signal_name"] = f"xgb_conformal_{cov}"
        signals_df["window_id"] = w_id

        # Simulate with carried equity0
        sim_window = simulate_daily(
            df_feat=pred_df,
            signals_df=signals_df,
            commission_bps=float(commission_bps),
            slippage_k=float(slippage_k),
            initial_equity=float(equity0),
        )

        # Keep only TEST dates (robust against off-by-one)
        test_start_date = pd.to_datetime(df_feat.iloc[ts]["date"])
        test_end_date = pd.to_datetime(df_feat.iloc[te]["date"])

        sim_window["date"] = pd.to_datetime(sim_window["date"])
        sim_test = sim_window[(sim_window["date"] >= test_start_date) & (sim_window["date"] <= test_end_date)].copy()
        if sim_test.empty:
            raise RuntimeError(f"Empty OOS simulation for window {w_id}.")

        sim_test = sim_test.reset_index(drop=True)
        sim_test["window_id"] = w_id
        sim_test["train_start_date"] = pd.to_datetime(df_feat.iloc[tr_s]["date"])
        sim_test["train_end_date"] = pd.to_datetime(df_feat.iloc[tr_e]["date"])
        sim_test["test_start_date"] = test_start_date
        sim_test["test_end_date"] = test_end_date
        sim_test["qhat"] = float(qhat)

        # Carry equity forward
        equity0 = float(sim_test["equity"].iloc[-1])

        # Per-window metrics (already correct equity)
        m = compute_metrics(sim_test)
        window_rows.append(
            {
                "window_id": w_id,
                "train_start": str(df_feat.iloc[tr_s]["date"]),
                "train_end": str(df_feat.iloc[tr_e]["date"]),
                "test_start": str(df_feat.iloc[ts]["date"]),
                "test_end": str(df_feat.iloc[te]["date"]),
                "n_train": int(tr_e - tr_s + 1),
                "n_test": int(te - ts + 1),
                "calib_size_used": int(len(calib_df)),
                "alpha": float(alpha),
                "qhat": float(qhat),
                **m,
            }
        )

        # Save OOS predictions/signals only for TEST dates
        pred_df["date"] = pd.to_datetime(pred_df["date"])
        pred_oos = pred_df[(pred_df["date"] >= test_start_date) & (pred_df["date"] <= test_end_date)].copy()
        pred_cols = [
            "date", "ticker", "y", "y_pred",
            f"y_lo_{cov}", f"y_hi_{cov}", f"width_{cov}",
            "qhat", "market_regime", "realized_vol", "window_id",
        ]
        pred_oos = pred_oos[pred_cols].copy()

        sig_oos = signals_df.copy()
        sig_oos["date"] = pd.to_datetime(sig_oos["date"])
        sig_oos = sig_oos[(sig_oos["date"] >= test_start_date) & (sig_oos["date"] <= test_end_date)].copy()
        sig_oos = sig_oos.reset_index(drop=True)

        all_preds.append(pred_oos)
        all_signals.append(sig_oos)
        all_oos_sims.append(sim_test)

    sim_oos_df = pd.concat(all_oos_sims, ignore_index=True)
    window_metrics_df = pd.DataFrame(window_rows)
    predictions_oos_df = pd.concat(all_preds, ignore_index=True)
    signals_oos_df = pd.concat(all_signals, ignore_index=True)

    run_metrics = compute_metrics(sim_oos_df)

    return sim_oos_df, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
