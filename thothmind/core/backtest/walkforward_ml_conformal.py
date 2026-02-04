from __future__ import annotations

import numpy as np
import pandas as pd

from thothmind.core.backtest.metrics import compute_metrics
from thothmind.core.backtest.simulator import simulate_daily
from thothmind.core.decision.allocation import conformal_to_exposure
from thothmind.core.models.xgb_regressor import XGBConfig, XGBReturnRegressor
from thothmind.core.models.conformal import conformal_qhat, conformal_interval


def _add_continuous_equity(sim_df: pd.DataFrame, initial_equity: float = 1.0) -> pd.DataFrame:
    df = sim_df.copy().sort_values("date").reset_index(drop=True)
    equity = [float(initial_equity)]
    for i in range(1, len(df)):
        equity.append(equity[-1] * (1.0 + float(df.loc[i, "pnl"])))
    df["equity"] = equity
    roll_max = df["equity"].cummax()
    df["drawdown"] = df["equity"] / roll_max - 1.0
    return df


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

    For each window:
      - Train on train
      - Calibration is the last `calib_size` samples of train (time-respecting)
      - Compute qhat from |y_cal - yhat_cal|
      - Predict on warmup+test, build [lo, hi] intervals
      - Convert intervals to exposure with uncertainty gating
      - Simulate only test days

    Returns:
      sim_oos_cont, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
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

    all_oos_sims = []
    window_rows = []
    all_preds = []
    all_signals = []

    for w_id, sp in enumerate(splits, start=1):
        tr_s = int(sp["train_start"])
        tr_e = int(sp["train_end"])
        ts = int(sp["test_start"])
        te = int(sp["test_end"])

        warmup = tr_e  # = test_start - 1

        train_df = df_feat.iloc[tr_s : tr_e + 1].copy()
        n_train = len(train_df)

        # Calibration slice (time-respecting): last calib_size points of train
        use_calib = min(calib_size, n_train)
        if use_calib < min_calib:
            # Too little calibration -> fallback to using half of train as calib
            use_calib = max(min_calib, n_train // 2)

        calib_df = train_df.iloc[-use_calib:].copy()
        fit_df = train_df.iloc[: n_train - use_calib].copy()

        # If fit_df becomes too small, merge back (robustness)
        if len(fit_df) < 50:
            fit_df = train_df.iloc[: n_train - min_calib].copy()
            calib_df = train_df.iloc[-min_calib:].copy()

        # Fit model on fit_df
        model = XGBReturnRegressor(xgb_cfg)
        model.fit(fit_df[feature_cols], fit_df["y"])

        # Calibrate
        yhat_cal = model.predict(calib_df[feature_cols])
        abs_res = np.abs(calib_df["y"].to_numpy(dtype=float) - yhat_cal)
        qhat = conformal_qhat(abs_res, alpha=alpha)

        # Predict for warmup+test
        pred_df = df_feat.iloc[warmup : te + 1].copy().reset_index(drop=True)
        y_pred = model.predict(pred_df[feature_cols])

        y_lo, y_hi = conformal_interval(y_pred, qhat)
        exp = conformal_to_exposure(y_pred=y_pred, y_lo=y_lo, y_hi=y_hi)

        pred_df["y_pred"] = y_pred
        pred_df[f"y_lo_{int((1-alpha)*100)}"] = y_lo
        pred_df[f"y_hi_{int((1-alpha)*100)}"] = y_hi
        pred_df[f"width_{int((1-alpha)*100)}"] = (y_hi - y_lo)
        pred_df["qhat"] = float(qhat)
        pred_df["window_id"] = w_id

        signals_df = pred_df[["date"]].copy()
        signals_df["target_exposure"] = exp
        signals_df["signal_name"] = f"xgb_conformal_{int((1-alpha)*100)}"
        signals_df["window_id"] = w_id

        sim_window = simulate_daily(
            df_feat=pred_df,
            signals_df=signals_df.rename(columns={"window_id": "window_id_sig"}),
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            initial_equity=float(initial_equity),
        )

        sim_test = sim_window.iloc[1:].copy().reset_index(drop=True)
        sim_test["window_id"] = w_id
        sim_test["train_start_date"] = pd.to_datetime(df_feat.iloc[tr_s]["date"])
        sim_test["train_end_date"] = pd.to_datetime(df_feat.iloc[tr_e]["date"])
        sim_test["test_start_date"] = pd.to_datetime(df_feat.iloc[ts]["date"])
        sim_test["test_end_date"] = pd.to_datetime(df_feat.iloc[te]["date"])

        sim_test = sim_test.rename(columns={"equity": "window_equity", "drawdown": "window_drawdown"})

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
                "calib_size_used": int(len(calib_df)),
                "alpha": float(alpha),
                "qhat": float(qhat),
                **m,
            }
        )

        pred_oos = pred_df.iloc[1:].copy().reset_index(drop=True)
        pred_cols = [
            "date", "ticker", "y", "y_pred",
            f"y_lo_{int((1-alpha)*100)}",
            f"y_hi_{int((1-alpha)*100)}",
            f"width_{int((1-alpha)*100)}",
            "qhat", "market_regime", "realized_vol", "window_id",
        ]
        pred_oos = pred_oos[pred_cols].copy()

        sig_oos = signals_df.iloc[1:].copy().reset_index(drop=True)
        sig_oos["window_id"] = w_id

        all_preds.append(pred_oos)
        all_signals.append(sig_oos)
        all_oos_sims.append(sim_test)

    sim_oos = pd.concat(all_oos_sims, ignore_index=True)
    window_metrics_df = pd.DataFrame(window_rows)
    predictions_oos_df = pd.concat(all_preds, ignore_index=True)
    signals_oos_df = pd.concat(all_signals, ignore_index=True)

    sim_oos_cont = sim_oos.copy()
    sim_oos_cont["equity"] = np.nan
    sim_oos_cont["drawdown"] = np.nan
    sim_oos_cont = _add_continuous_equity(sim_oos_cont, initial_equity=float(initial_equity))

    run_metrics = compute_metrics(sim_oos_cont)

    return sim_oos_cont, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
