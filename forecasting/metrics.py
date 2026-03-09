from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from data.metrics.performance import compute_performance_metrics


def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Evaluate regression quality.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    mae = float(mean_absolute_error(y_true, y_pred))

    mask = y_true != 0
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0) if mask.any() else np.nan

    return {
        "r2": float(r2_score(y_true, y_pred)),
        "rmse": rmse,
        "mae": mae,
        "mape": mape,
    }


def print_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> None:
    """
    Backward-compatible pretty printer used by old scripts.
    """
    metrics = evaluate_regression(y_true, y_pred)

    print("\n📊 Regression metrics:")
    print(f"- R²:   {metrics['r2']:.4f}")
    print(f"- RMSE: {metrics['rmse']:.6f}")
    print(f"- MAE:  {metrics['mae']:.6f}")
    if np.isnan(metrics["mape"]):
        print("- MAPE: n/a (true values contain zeros)")
    else:
        print(f"- MAPE: {metrics['mape']:.2f}%")


def evaluate_strategy(
    df: pd.DataFrame,
    *,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> dict:
    """
    Evaluate trading strategy performance from a simulation dataframe.
    """
    if "strategy_return" not in df.columns:
        raise KeyError("evaluate_strategy() expects a 'strategy_return' column.")

    metrics = compute_performance_metrics(
        df["strategy_return"],
        periods_per_year=periods_per_year,
        risk_free_rate=risk_free_rate,
        enforce_returns_input=True,
    )

    if "capital" in df.columns and not df["capital"].dropna().empty:
        metrics["total_return"] = float(df["capital"].dropna().iloc[-1] - 1.0)

    if "signal" in df.columns:
        metrics["trades"] = int(pd.to_numeric(df["signal"], errors="coerce").fillna(0).sum())
    else:
        metrics["trades"] = 0

    if "executed_entry" in df.columns:
        metrics["executed_entries"] = int(pd.to_numeric(df["executed_entry"], errors="coerce").fillna(0).sum())
    else:
        metrics["executed_entries"] = metrics["trades"]

    if "position" in df.columns:
        metrics["exposure_days"] = int((pd.to_numeric(df["position"], errors="coerce").fillna(0) > 0).sum())
    else:
        metrics["exposure_days"] = 0

    return metrics