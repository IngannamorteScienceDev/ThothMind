from __future__ import annotations

import numpy as np
import pandas as pd


def _to_series(values) -> pd.Series:
    if isinstance(values, pd.Series):
        series = values.copy()
    else:
        series = pd.Series(values)

    return pd.to_numeric(series, errors="coerce").dropna()


def _looks_like_equity_curve(series: pd.Series) -> bool:
    """
    Heuristic guard against accidentally passing capital/equity instead of returns.
    """
    if len(series) < 3:
        return False

    s = series.dropna().astype(float)
    if s.empty:
        return False

    starts_near_one = 0.5 <= float(s.iloc[0]) <= 1.5
    strictly_positive = bool((s > 0).all())
    mostly_non_decreasing = bool((s.diff().dropna() >= 0).mean() > 0.7)
    ends_above_one = float(s.iloc[-1]) > 1.1 or float(s.max()) > 2.0

    return starts_near_one and strictly_positive and mostly_non_decreasing and ends_above_one


def compute_performance_metrics(
    returns: pd.Series,
    *,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
    enforce_returns_input: bool = True,
) -> dict:
    """
    Compute metrics from a per-period returns series.

    IMPORTANT: do not pass capital/equity here.
    """
    ret = _to_series(returns)

    if ret.empty:
        return {
            "total_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "mean_return": 0.0,
            "win_rate": 0.0,
            "n_periods": 0,
        }

    if enforce_returns_input and _looks_like_equity_curve(ret):
        raise ValueError(
            "compute_performance_metrics() expects a returns series, but received "
            "data that looks like an equity/capital curve."
        )

    if (ret <= -1.0).any():
        raise ValueError("Returns series contains values <= -100%, which is invalid.")

    cumulative = (1.0 + ret).cumprod()
    total_return = float(cumulative.iloc[-1] - 1.0)

    mean_return = float(ret.mean())
    volatility = float(ret.std(ddof=0))

    excess_returns = ret - risk_free_rate
    excess_std = float(excess_returns.std(ddof=0))
    sharpe = float(np.sqrt(periods_per_year) * excess_returns.mean() / excess_std) if excess_std > 0 else 0.0

    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1.0
    max_drawdown = float(drawdown.min())

    win_rate = float((ret > 0).mean())

    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "mean_return": mean_return,
        "win_rate": win_rate,
        "n_periods": int(len(ret)),
    }