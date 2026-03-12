from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from data.metrics.performance import compute_performance_metrics
from thothmind.core.backtest.walkforward_ml import (
    _build_policy,
    _first_existing_col,
    _generate_walkforward_slices,
    _infer_feature_cols,
    _infer_target_col,
    _run_metrics_from_sim,
    _resolve_runtime_configs,
)
from thothmind.core.execution.position import attach_equity_curve, build_long_only_positions, compute_dynamic_thresholds, resolve_return_col


class WalkforwardConformalResult(dict):
    """
    Dict-like result that is also tuple-unpackable.

    run.py expects unpack order:
    sim_oos, window_metrics, predictions_oos, signals_oos, run_metrics
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __iter__(self):
        yield self["sim_oos"]
        yield self["window_metrics"]
        yield self["predictions_oos"]
        yield self["signals_oos"]
        yield self["run_metrics"]


def _build_xgb(model_cfg: dict[str, Any] | None) -> XGBRegressor:
    cfg = dict(model_cfg or {})
    xgb_params = cfg.pop("xgb_params", {}) if isinstance(cfg.get("xgb_params"), dict) else {}

    params = {
        "n_estimators": int(cfg.get("n_estimators", xgb_params.get("n_estimators", 250))),
        "max_depth": int(cfg.get("max_depth", xgb_params.get("max_depth", 4))),
        "learning_rate": float(cfg.get("learning_rate", xgb_params.get("learning_rate", 0.05))),
        "subsample": float(cfg.get("subsample", xgb_params.get("subsample", 0.9))),
        "colsample_bytree": float(cfg.get("colsample_bytree", xgb_params.get("colsample_bytree", 0.9))),
        "min_child_weight": float(cfg.get("min_child_weight", xgb_params.get("min_child_weight", 1.0))),
        "reg_alpha": float(cfg.get("reg_alpha", xgb_params.get("reg_alpha", 0.0))),
        "reg_lambda": float(cfg.get("reg_lambda", xgb_params.get("reg_lambda", 1.0))),
        "random_state": int(cfg.get("random_state", xgb_params.get("random_state", 42))),
        "objective": "reg:squarederror",
        "n_jobs": int(cfg.get("n_jobs", xgb_params.get("n_jobs", -1))),
    }
    return XGBRegressor(**params)


def _split_train_and_calibration(
    train_df: pd.DataFrame,
    *,
    calib_frac: float,
    calib_size: int | None,
    min_calib: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(train_df)
    if n < 80:
        raise ValueError("Conformal split requires a larger train window.")

    if calib_size is None:
        frac = min(max(float(calib_frac), 0.05), 0.40)
        size = int(round(n * frac))
    else:
        size = int(calib_size)

    if min_calib is not None:
        size = max(size, int(min_calib))

    size = max(20, size)
    size = min(size, max(10, n // 3))
    size = min(size, n - 50)

    proper_train = train_df.iloc[: n - size].copy()
    calib = train_df.iloc[n - size :].copy()
    if proper_train.empty or calib.empty:
        raise ValueError("Conformal split produced empty proper-train or calibration subset.")
    return proper_train, calib


def _merge_decision_and_allocation(
    decision_cfg: dict[str, Any] | None,
    allocation_cfg: dict[str, Any] | None,
) -> dict[str, Any]:
    d = dict(decision_cfg or {})
    a = dict(allocation_cfg or {})
    if not a:
        return d

    if "min_hold_bars" not in d and "min_hold_days" in a:
        d["min_hold_bars"] = int(a["min_hold_days"])
    if "max_position" not in d and "high_exposure" in a:
        d["max_position"] = float(a["high_exposure"])
    if "min_position" not in d and "low_exposure" in a:
        d["min_position"] = float(a["low_exposure"])
    if "confidence_floor" not in d and "mid_exposure" in a:
        d["confidence_floor"] = max(0.25, min(float(a["mid_exposure"]), 1.0))
    return d


def run_walkforward_ml_conformal_oos(
    *,
    df_feat: pd.DataFrame,
    feature_cols: list[str] | None = None,
    model_cfg: dict[str, Any] | None = None,
    conformal_cfg: dict[str, Any] | None = None,
    allocation_cfg: dict[str, Any] | None = None,
    decision_cfg: dict[str, Any] | None = None,
    walkforward_cfg: dict[str, Any] | None = None,
    costs_cfg: dict[str, Any] | None = None,
    sim_cfg: dict[str, Any] | None = None,
    features_cfg: dict[str, Any] | None = None,
    target_col: str | None = None,
    target_column: str | None = None,
    label_col: str | None = None,
    y_col: str | None = None,
    horizon: int | None = None,
    step: int | None = None,
    splits: list[Any] | None = None,
    commission_bps: float | None = None,
    slippage_k: float | None = None,
    slippage_bps: float | None = None,
    slippage_vol_k: float | None = None,
    initial_equity: float | None = None,
    execution_lag: int | None = None,
    **_: Any,
) -> WalkforwardConformalResult:
    """
    Conformal ML walk-forward.

    Main upgrade:
    - strict conformal gate is handled inside build_long_only_positions
    - understands both config-dicts and legacy direct kwargs from run.py / suite code
    """
    if df_feat is None or df_feat.empty:
        raise ValueError("df_feat is empty; conformal walk-forward cannot run.")

    wf, costs, sim, features_cfg, resolved_splits = _resolve_runtime_configs(
        walkforward_cfg=walkforward_cfg,
        costs_cfg=costs_cfg,
        sim_cfg=sim_cfg,
        features_cfg=features_cfg,
        splits=splits,
        commission_bps=commission_bps,
        slippage_k=slippage_k,
        slippage_bps=slippage_bps,
        slippage_vol_k=slippage_vol_k,
        initial_equity=initial_equity,
        execution_lag=execution_lag,
        step=step,
        n_rows=len(df_feat),
    )
    model_cfg = dict(model_cfg or {})
    conformal_cfg = dict(conformal_cfg or {})

    initial_equity = float(sim.get("initial_equity", 1.0))
    commission_bps = float(costs.get("commission_bps", 2.0))
    slippage_k = float(costs.get("slippage_k", 0.15))

    conformal_alpha = float(conformal_cfg.get("alpha", model_cfg.get("conformal_alpha", 0.10)))
    calibration_frac = float(model_cfg.get("conformal_calibration_frac", 0.20))
    calib_size = conformal_cfg.get("calib_size")
    min_calib = conformal_cfg.get("min_calib")

    df = df_feat.copy().sort_values("date").reset_index(drop=True)
    explicit_target = target_col or target_column or label_col or y_col
    cfg_horizon = int(horizon) if horizon is not None else (int(features_cfg["horizon"]) if features_cfg.get("horizon") is not None else None)
    target_col = _infer_target_col(df, explicit_target_col=explicit_target, horizon=cfg_horizon)
    ret_col = resolve_return_col(df)

    if feature_cols is None:
        feature_cols = _infer_feature_cols(df, target_col)
    else:
        feature_cols = [c for c in feature_cols if c in df.columns]

    if not resolved_splits:
        raise ValueError("No walk-forward slices could be built. Check train/test/step sizes.")

    eff_decision_cfg = _merge_decision_and_allocation(decision_cfg, allocation_cfg)
    policy = _build_policy(eff_decision_cfg, sim)

    pred_parts: list[pd.DataFrame] = []
    sim_parts: list[pd.DataFrame] = []
    win_rows: list[dict[str, Any]] = []
    rolling_equity = initial_equity

    for window_id, (tr_s, tr_e, te_s, te_e) in enumerate(resolved_splits, start=1):
        train_df = df.iloc[tr_s:tr_e].copy()
        test_df = df.iloc[te_s:te_e].copy()
        proper_train, calib_df = _split_train_and_calibration(
            train_df,
            calib_frac=calibration_frac,
            calib_size=int(calib_size) if calib_size is not None else None,
            min_calib=int(min_calib) if min_calib is not None else None,
        )

        X_proper = proper_train[feature_cols].astype(float)
        y_proper = pd.to_numeric(proper_train[target_col], errors="coerce").astype(float)
        X_cal = calib_df[feature_cols].astype(float)
        y_cal = pd.to_numeric(calib_df[target_col], errors="coerce").astype(float)
        X_test = test_df[feature_cols].astype(float)
        y_test = pd.to_numeric(test_df[target_col], errors="coerce").astype(float)

        model = _build_xgb(model_cfg)
        model.fit(X_proper, y_proper)

        pred_cal = model.predict(X_cal)
        abs_residuals = np.abs(y_cal.to_numpy() - pred_cal)
        q = float(np.quantile(abs_residuals, min(max(1.0 - conformal_alpha, 0.5), 0.99)))

        test_pred = model.predict(X_test)
        test_lo = test_pred - q
        test_hi = test_pred + q

        enter_thr, exit_thr = compute_dynamic_thresholds(
            pred_cal,
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            enter_quantile=policy.enter_quantile,
            exit_quantile=policy.exit_quantile,
            edge_buffer_bps=policy.edge_buffer_bps,
        )

        pred_span = test_df.copy()
        pred_span["window_id"] = window_id
        pred_span["pred"] = test_pred
        pred_span["pred_lo"] = test_lo
        pred_span["pred_hi"] = test_hi
        pred_span["conf_radius"] = q
        pred_span["y_true"] = y_test.to_numpy()

        pred_parts.append(
            pred_span[
                [
                    c
                    for c in [
                        "date",
                        "window_id",
                        "pred",
                        "pred_lo",
                        "pred_hi",
                        "conf_radius",
                        "y_true",
                        target_col,
                        ret_col,
                        "market_regime",
                    ]
                    if c in pred_span.columns
                ]
            ].copy()
        )

        sig_span = build_long_only_positions(
            pred_span,
            prediction_col="pred",
            lower_bound_col="pred_lo",
            regime_col="market_regime",
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            enter_threshold=enter_thr,
            exit_threshold=exit_thr,
            policy=policy,
        )
        sig_span["window_id"] = window_id

        sim_span = attach_equity_curve(sig_span, initial_equity=rolling_equity)
        sim_span["window_id"] = window_id
        sim_parts.append(sim_span.copy())

        window_metrics = compute_performance_metrics(sim_span["net_ret"], periods_per_year=252, enforce_returns_input=True)
        win_rows.append(
            {
                "window_id": window_id,
                "train_start_idx": tr_s,
                "train_end_idx": tr_e - 1,
                "test_start_idx": te_s,
                "test_end_idx": te_e - 1,
                "train_start_date": str(train_df["date"].iloc[0]),
                "train_end_date": str(train_df["date"].iloc[-1]),
                "test_start_date": str(test_df["date"].iloc[0]),
                "test_end_date": str(test_df["date"].iloc[-1]),
                "conformal_alpha": float(conformal_alpha),
                "conf_radius": float(q),
                "enter_threshold": float(enter_thr),
                "exit_threshold": float(exit_thr),
                "mean_pred_test": float(np.mean(test_pred)),
                "mean_pred_lo_test": float(np.mean(test_lo)),
                "median_pred_test": float(np.median(test_pred)),
                "trades": int(sig_span.get("execution_entry_signal", sig_span["signal"]).sum()),
                "avg_exposure": float(sig_span["position"].mean()),
                "window_sharpe": float(window_metrics.get("sharpe", 0.0)),
                "window_max_drawdown": float(window_metrics.get("max_drawdown", 0.0)),
            }
        )
        rolling_equity = float(sim_span["equity"].iloc[-1])

    predictions_oos = pd.concat(pred_parts, ignore_index=True).sort_values("date").reset_index(drop=True)
    sim_oos = pd.concat(sim_parts, ignore_index=True).sort_values("date").reset_index(drop=True)
    signals_oos = sim_oos.copy()
    window_metrics_df = pd.DataFrame(win_rows)
    run_metrics = _run_metrics_from_sim(sim_oos)

    return WalkforwardConformalResult(
        predictions_oos=predictions_oos,
        signals_oos=signals_oos,
        sim_oos=sim_oos,
        window_metrics=window_metrics_df,
        run_metrics=run_metrics,
        feature_cols=feature_cols,
    )


run_walkforward_ml_conformal = run_walkforward_ml_conformal_oos
