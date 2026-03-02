from __future__ import annotations

import numpy as np
import pandas as pd

from thothmind.core.backtest.metrics import compute_metrics
from thothmind.core.backtest.simulator import simulate_daily
from thothmind.core.decision.allocation import conformal_to_exposure
from thothmind.core.models.conformal import conformal_interval, conformal_qhat
from thothmind.core.models.xgb_regressor import XGBConfig, XGBReturnRegressor


def run_walkforward_ml_conformal_oos(
    df_feat: pd.DataFrame,
    feature_cols: list[str],
    splits: list[dict],
    model_cfg: dict,
    conformal_cfg: dict,
    commission_bps: float,
    slippage_bps: float,
    slippage_vol_k: float,
    initial_equity: float = 1.0,
    execution_lag: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Walk-forward ML + split conformal intervals.
    Costs use new schema: slippage in bps + volatility scaling.
    Equity is stitched window-to-window.

    execution_lag:
      - 0: execute same day (exposure_t = target_exposure_t)
      - 1: execute next day (exposure_t = target_exposure_{t-1}) to avoid lookahead

    Returns:
      sim_oos_df, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
    """
    df_feat = df_feat.copy().sort_values("date").reset_index(drop=True)
    df_feat["date"] = pd.to_datetime(df_feat["date"])

    alpha = float((conformal_cfg or {}).get("alpha", 0.10))
    calib_size = int((conformal_cfg or {}).get("calib_size", 252))
    min_calib = int((conformal_cfg or {}).get("min_calib", 126))

    xgb_cfg = XGBConfig(
        n_estimators=int((model_cfg or {}).get("n_estimators", 600)),
        max_depth=int((model_cfg or {}).get("max_depth", 4)),
        learning_rate=float((model_cfg or {}).get("learning_rate", 0.03)),
        subsample=float((model_cfg or {}).get("subsample", 0.8)),
        colsample_bytree=float((model_cfg or {}).get("colsample_bytree", 0.8)),
        reg_lambda=float((model_cfg or {}).get("reg_lambda", 1.0)),
        min_child_weight=float((model_cfg or {}).get("min_child_weight", 1.0)),
        random_state=int((model_cfg or {}).get("random_state", 42)),
    )

    all_oos_sims: list[pd.DataFrame] = []
    window_rows: list[dict] = []
    all_preds: list[pd.DataFrame] = []
    all_signals: list[pd.DataFrame] = []

    equity0 = float(initial_equity)
    cov = int((1.0 - alpha) * 100)

    lag = int(execution_lag)
    if lag < 0:
        raise ValueError("execution_lag must be >= 0")

    for w_id, sp in enumerate(splits, start=1):
        tr_s = int(sp["train_start"])
        tr_e = int(sp["train_end"])
        ts = int(sp["test_start"])
        te = int(sp["test_end"])

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

        # Conformal calibration
        yhat_cal = model.predict(calib_df[feature_cols])
        abs_res = np.abs(calib_df["y"].to_numpy(dtype=float) - yhat_cal)
        qhat = conformal_qhat(abs_res, alpha=alpha)

        # Predict on (train_end..test_end) span, then keep only OOS dates later
        pred_span = df_feat.iloc[tr_e : te + 1].copy().reset_index(drop=True)

        y_pred = model.predict(pred_span[feature_cols])
        y_lo, y_hi = conformal_interval(y_pred, qhat=qhat)

        # --- Allocation (configurable) ---
        alloc_cfg = (conformal_cfg or {})  # flat keys

        low_exposure = float(alloc_cfg.get("low_exposure", 0.0))
        mid_exposure = float(alloc_cfg.get("mid_exposure", 0.5))
        high_exposure = float(alloc_cfg.get("high_exposure", 1.0))

        y_pred_thr = float(alloc_cfg.get("y_pred_thr", 0.0))
        width_max = alloc_cfg.get("width_max", None)
        width_max = float(width_max) if width_max is not None else None

        min_hold_days = int(alloc_cfg.get("min_hold_days", 0))

        exp = conformal_to_exposure(
            y_pred=y_pred,
            y_lo=y_lo,
            y_hi=y_hi,
            low_exposure=low_exposure,
            mid_exposure=mid_exposure,
            high_exposure=high_exposure,
            y_pred_thr=y_pred_thr,
            width_max=width_max,
            min_hold_days=min_hold_days,
            clip_min=0.0,
            clip_max=1.0,
        )

        pred_span["y_pred"] = y_pred
        pred_span[f"y_lo_{cov}"] = y_lo
        pred_span[f"y_hi_{cov}"] = y_hi
        pred_span[f"width_{cov}"] = (y_hi - y_lo)
        pred_span["qhat"] = float(qhat)
        pred_span["window_id"] = w_id

        signals_span = pred_span[["date"]].copy()
        signals_span["target_exposure"] = exp
        signals_span["signal_name"] = f"xgb_conformal_{cov}"
        signals_span["window_id"] = w_id

        # Simulate over the full span to handle turnover correctly, then slice OOS
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
        sim_oos["qhat"] = float(qhat)

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
                "calib_size_used": int(len(calib_df)),
                "alpha": float(alpha),
                "qhat": float(qhat),
                "execution_lag": int(lag),
                **m,
            }
        )

        # Save OOS preds/signals only
        pred_span["date"] = pd.to_datetime(pred_span["date"])
        pred_oos = pred_span[(pred_span["date"] >= test_start_date) & (pred_span["date"] <= test_end_date)].copy()
        keep_cols = [
            "date", "ticker", "y", "y_pred",
            f"y_lo_{cov}", f"y_hi_{cov}", f"width_{cov}",
            "qhat", "window_id",
        ]
        keep_cols = [c for c in keep_cols if c in pred_oos.columns]
        pred_oos = pred_oos[keep_cols].copy()

        sig_oos = signals_span.copy()
        sig_oos["date"] = pd.to_datetime(sig_oos["date"])
        sig_oos = sig_oos[(sig_oos["date"] >= test_start_date) & (sig_oos["date"] <= test_end_date)].copy().reset_index(drop=True)

        all_oos_sims.append(sim_oos)
        all_preds.append(pred_oos)
        all_signals.append(sig_oos)

    sim_oos_df = pd.concat(all_oos_sims, ignore_index=True)
    window_metrics_df = pd.DataFrame(window_rows)
    predictions_oos_df = pd.concat(all_preds, ignore_index=True) if all_preds else pd.DataFrame()
    signals_oos_df = pd.concat(all_signals, ignore_index=True) if all_signals else pd.DataFrame()

    run_metrics = compute_metrics(sim_oos_df)
    run_metrics["allocation"] = {
        "low_exposure": float(low_exposure),
        "mid_exposure": float(mid_exposure),
        "high_exposure": float(high_exposure),
        "y_pred_thr": float(y_pred_thr),
        "width_max": None if width_max is None else float(width_max),
        "min_hold_days": int(min_hold_days),
    }
    return sim_oos_df, window_metrics_df, predictions_oos_df, signals_oos_df, run_metrics
