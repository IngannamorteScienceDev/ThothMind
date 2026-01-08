import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score
)

# =========================
# Regression model metrics
# =========================

def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Evaluate regression model quality.

    Returns:
        dict with R2, RMSE, MAE, MAPE
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true, y_pred)

    # Avoid division by zero in MAPE
    mask = y_true != 0
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

    return {
        "r2": r2_score(y_true, y_pred),
        "rmse": rmse,
        "mae": mae,
        "mape": mape
    }


# =========================
# Trading strategy metrics
# =========================

def evaluate_strategy(df: pd.DataFrame, risk_free_rate: float = 0.0) -> dict:
    """
    Evaluate trading strategy performance.

    Expects df with columns:
    - strategy_return
    - capital

    Returns:
        dict with total_return, sharpe_ratio, max_drawdown
    """
    returns = df["strategy_return"].dropna()

    total_return = df["capital"].iloc[-1] - 1

    # Sharpe Ratio
    excess_returns = returns - risk_free_rate
    sharpe = (
        np.sqrt(252) * excess_returns.mean() / excess_returns.std()
        if excess_returns.std() != 0 else 0.0
    )

    # Max Drawdown
    cumulative = df["capital"]
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()

    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown
    }
