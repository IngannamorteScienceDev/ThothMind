from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from data.metrics.performance import compute_performance_metrics
from thothmind.core.execution.position import (
    PositionPolicyConfig,
    attach_equity_curve,
    build_long_only_positions,
    compute_dynamic_thresholds,
    resolve_return_col,
)


class WalkforwardResult(dict):
    """
    Dict-like result that is also tuple-unpackable.

    Expected unpack order for run.py:
    predictions_oos, sim_oos, signals_oos, window_metrics, feature_cols
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __iter__(self):
        yield self["predictions_oos"]
        yield self["sim_oos"]
        yield self["signals_oos"]
        yield self["window_metrics"]
        yield self["feature_cols"]


def _first_existing_col(df: pd.DataFrame, names: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in df.columns}
    for name in names:
        if name in df.columns:
            return name
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def _infer_target_col(
    df: pd.DataFrame,
    *,
    explicit_target_col: str | None = None,
    horizon: int | None = None,
) -> str:
    if explicit_target_col and explicit_target_col in df.columns:
        return explicit_target_col

    candidates: list[str] = []

    if explicit_target_col:
        candidates.append(explicit_target_col)

    if horizon is not None:
        h = int(horizon)
        candidates.extend(
            [
                f"target_return_{h}d",
                f"target_return_{h}",
                f"future_return_{h}d",
                f"future_return_{h}",
                f"forward_return_{h}d",
                f"forward_return_{h}",
                f"fwd_return_{h}d",
                f"fwd_return_{h}",
                f"label_return_{h}d",
                f"label_return_{h}",
                f"target_{h}d",
                f"target_{h}",
                f"y_{h}d",
                f"y_{h}",
            ]
        )

    candidates.extend(
        [
            "target",
            "y",
            "label",
            "y_reg",
            "label_reg",
            "target_reg",
            "target_return",
            "future_return",
            "forward_return",
            "fwd_return",
            "next_return",
            "y_return",
            "label_return",
        ]
    )

    col = _first_existing_col(df, candidates)
    if col is not None:
        return col

    forbidden_exact = {
        "return_1d",
        "ret_1d",
        "daily_return",
        "gross_ret",
        "net_ret",
        "strategy_return",
        "actual_return",
    }

    heuristic_candidates: list[str] = []
    for c in df.columns:
        lc = c.lower()
        if lc in forbidden_exact:
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        if any(tok in lc for tok in ["target", "label", "future", "forward", "fwd", "next"]) or lc in {
            "y",
            "y_reg",
        }:
            heuristic_candidates.append(c)

    if heuristic_candidates:
        return heuristic_candidates[0]

    raise KeyError("Could not infer target column.")


def _infer_feature_cols(df: pd.DataFrame, target_col: str) -> list[str]:
    forbidden_prefixes = (
        "target",
        "pred",
        "signal",
        "position",
        "equity",
        "capital",
        "drawdown",
        "commission",
        "slippage",
        "gross_ret",
        "net_ret",
        "total_cost",
    )
    forbidden_exact = {
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "openint",
        "ticker",
        "market_regime",
        "regime",
    }

    feature_cols: list[str] = []
    for col in df.columns:
        lc = col.lower()
        if col == target_col:
            continue
        if lc in forbidden_exact:
            continue
        if lc.startswith(forbidden_prefixes):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            feature_cols.append(col)

    if not feature_cols:
        raise ValueError("No numeric feature columns inferred for walk-forward ML stage.")

    return feature_cols


def _generate_walkforward_slices(
    n_rows: int,
    *,
    train_size: int,
    test_size: int,
    step: int,
) -> list[tuple[int, int, int, int]]:
    slices: list[tuple[int, int, int, int]] = []
    start = 0
    while start + train_size + test_size <= n_rows:
        tr_s = start
        tr_e = start + train_size
        te_s = tr_e
        te_e = te_s + test_size
        slices.append((tr_s, tr_e, te_s, te_e))
        start += step
    return slices


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


def _build_policy(decision_cfg: dict[str, Any] | None, sim_cfg: dict[str, Any] | None) -> PositionPolicyConfig:
    d = dict(decision_cfg or {})
    s = dict(sim_cfg or {})
    return PositionPolicyConfig(
        enter_quantile=float(d.get("enter_quantile", 0.70)),
        exit_quantile=float(d.get("exit_quantile", 0.45)),
        edge_buffer_bps=float(d.get("edge_buffer_bps", 5.0)),
        min_hold_bars=int(d.get("min_hold_bars", 5)),
        cooldown_bars=int(d.get("cooldown_bars", 3)),
        trend_sma_window=int(d.get("trend_sma_window", 200)),
        use_trend_filter=bool(d.get("use_trend_filter", True)),
        block_regimes=tuple(d.get("block_regimes", ["Bear_HighVol"])),
        vol_target_annual=float(d.get("vol_target_annual", 0.18)),
        vol_lookback=int(d.get("vol_lookback", 20)),
        max_position=float(d.get("max_position", 1.0)),
        min_position=float(d.get("min_position", 0.0)),
        confidence_floor=float(d.get("confidence_floor", 0.25)),
        confidence_cap=float(d.get("confidence_cap", 1.0)),
        execution_lag=int(s.get("execution_lag", 1)),
    )


def _run_metrics_from_sim(sim_oos: pd.DataFrame) -> dict[str, Any]:
    metrics = compute_performance_metrics(
        sim_oos["net_ret"],
        periods_per_year=252,
        enforce_returns_input=True,
    )
    metrics["total_return"] = float(sim_oos["equity"].iloc[-1] - 1.0) if not sim_oos.empty else 0.0
    metrics["total_return_pct"] = metrics["total_return"] * 100.0
    metrics["sharpe"] = float(metrics.get("sharpe", 0.0))
    metrics["max_drawdown"] = float(metrics.get("max_drawdown", 0.0))
    metrics["max_drawdown_pct"] = metrics["max_drawdown"] * 100.0
    metrics["mean_net_ret"] = (
        float(pd.to_numeric(sim_oos["net_ret"], errors="coerce").mean()) if not sim_oos.empty else 0.0
    )
    metrics["avg_exposure"] = (
        float(pd.to_numeric(sim_oos["position"], errors="coerce").mean()) if "position" in sim_oos.columns else 0.0
    )
    metrics["avg_turnover"] = (
        float(pd.to_numeric(sim_oos["turnover"], errors="coerce").mean()) if "turnover" in sim_oos.columns else 0.0
    )
    metrics["total_cost_sum"] = (
        float(pd.to_numeric(sim_oos["total_cost"], errors="coerce").sum()) if "total_cost" in sim_oos.columns else 0.0
    )
    metrics["n_days"] = int(len(sim_oos))
    return metrics


def run_walkforward_ml_oos(
    *,
    df_feat: pd.DataFrame,
    feature_cols: list[str] | None = None,
    model_cfg: dict[str, Any] | None = None,
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
    **_: Any,
) -> WalkforwardResult:
    """
    ML walk-forward with stronger policy layer:
    - dynamic thresholds from train-window prediction distribution
    - trend filter
    - volatility targeting
    - hysteresis
    """
    if df_feat is None or df_feat.empty:
        raise ValueError("df_feat is empty; walk-forward ML cannot run.")

    wf = dict(walkforward_cfg or {})
    costs = dict(costs_cfg or {})
    sim = dict(sim_cfg or {})

    train_size = int(wf.get("train_size", 756))
    test_size = int(wf.get("test_size", 63))
    step = int(step if step is not None else wf.get("step", test_size))
    initial_equity = float(sim.get("initial_equity", 1.0))
    commission_bps = float(costs.get("commission_bps", 2.0))
    slippage_k = float(costs.get("slippage_k", 0.15))

    df = df_feat.copy().sort_values("date").reset_index(drop=True)
    explicit_target = target_col or target_column or label_col or y_col

    cfg_horizon = None
    if horizon is not None:
        cfg_horizon = int(horizon)
    elif isinstance(features_cfg, dict) and features_cfg.get("horizon") is not None:
        cfg_horizon = int(features_cfg["horizon"])

    target_col = _infer_target_col(
        df,
        explicit_target_col=explicit_target,
        horizon=cfg_horizon,
    )
    ret_col = resolve_return_col(df)

    if feature_cols is None:
        feature_cols = _infer_feature_cols(df, target_col)
    else:
        feature_cols = [c for c in feature_cols if c in df.columns]

    slices = _generate_walkforward_slices(
        len(df),
        train_size=train_size,
        test_size=test_size,
        step=step,
    )
    if not slices:
        raise ValueError("No walk-forward slices could be built. Check train/test/step sizes.")

    policy = _build_policy(decision_cfg, sim_cfg)

    pred_parts: list[pd.DataFrame] = []
    sig_parts: list[pd.DataFrame] = []
    sim_parts: list[pd.DataFrame] = []
    win_rows: list[dict[str, Any]] = []

    rolling_equity = initial_equity

    for window_id, (tr_s, tr_e, te_s, te_e) in enumerate(slices, start=1):
        train_df = df.iloc[tr_s:tr_e].copy()
        test_df = df.iloc[te_s:te_e].copy()

        X_train = train_df[feature_cols].astype(float)
        y_train = pd.to_numeric(train_df[target_col], errors="coerce").astype(float)

        X_test = test_df[feature_cols].astype(float)
        y_test = pd.to_numeric(test_df[target_col], errors="coerce").astype(float)

        model = _build_xgb(model_cfg)
        model.fit(X_train, y_train)

        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)

        enter_thr, exit_thr = compute_dynamic_thresholds(
            train_pred,
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            enter_quantile=policy.enter_quantile,
            exit_quantile=policy.exit_quantile,
            edge_buffer_bps=policy.edge_buffer_bps,
        )

        pred_span = test_df.copy()
        pred_span["window_id"] = window_id
        pred_span["pred"] = test_pred
        pred_span["y_true"] = y_test.to_numpy()
        pred_span["target_col_name"] = target_col

        pred_parts.append(
            pred_span[
                [c for c in ["date", "window_id", "pred", "y_true", target_col, ret_col, "market_regime"] if c in pred_span.columns]
            ].copy()
        )

        sig_span = build_long_only_positions(
            pred_span,
            prediction_col="pred",
            lower_bound_col=None,
            regime_col="market_regime",
            commission_bps=commission_bps,
            slippage_k=slippage_k,
            enter_threshold=enter_thr,
            exit_threshold=exit_thr,
            policy=policy,
        )
        sig_span["window_id"] = window_id
        sig_parts.append(sig_span.copy())

        sim_span = attach_equity_curve(sig_span, initial_equity=rolling_equity)
        sim_span["window_id"] = window_id
        sim_parts.append(sim_span.copy())

        window_metrics = compute_performance_metrics(
            sim_span["net_ret"],
            periods_per_year=252,
            enforce_returns_input=True,
        )

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
                "enter_threshold": float(enter_thr),
                "exit_threshold": float(exit_thr),
                "mean_pred_test": float(np.mean(test_pred)),
                "median_pred_test": float(np.median(test_pred)),
                "trades": int(sig_span["signal"].sum()),
                "avg_exposure": float(sig_span["position"].mean()),
                "window_total_return": float(sim_span["equity"].iloc[-1] / rolling_equity - 1.0),
                "window_sharpe": float(window_metrics.get("sharpe", 0.0)),
                "window_max_drawdown": float(window_metrics.get("max_drawdown", 0.0)),
            }
        )

        rolling_equity = float(sim_span["equity"].iloc[-1])

    predictions_oos = pd.concat(pred_parts, ignore_index=True).sort_values("date").reset_index(drop=True)
    signals_oos = pd.concat(sig_parts, ignore_index=True).sort_values("date").reset_index(drop=True)
    sim_oos = pd.concat(sim_parts, ignore_index=True).sort_values("date").reset_index(drop=True)
    window_metrics_df = pd.DataFrame(win_rows)

    run_metrics = _run_metrics_from_sim(sim_oos)

    return WalkforwardResult(
        predictions_oos=predictions_oos,
        signals_oos=signals_oos,
        sim_oos=sim_oos,
        window_metrics=window_metrics_df,
        run_metrics=run_metrics,
        feature_cols=feature_cols,
    )


run_walkforward_ml = run_walkforward_ml_oos