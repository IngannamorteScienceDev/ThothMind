from __future__ import annotations

import numpy as np
import pandas as pd

from data.metrics.performance import compute_performance_metrics


def compute_inverse_vol_weights(
    returns_df: pd.DataFrame,
    alloc_map: dict,
    vol_lookback: int = 20,
    max_weight: float = 0.5,
) -> dict:
    """
    Build inverse-volatility weights for assets with positive allocation.
    """
    if returns_df.empty:
        return {"CASH": 1.0}

    vols = {}
    for ticker in returns_df.columns:
        alloc = float(alloc_map.get(ticker, 0.0))
        if alloc <= 0:
            continue

        vol = pd.to_numeric(returns_df[ticker], errors="coerce").rolling(vol_lookback).std().iloc[-1]
        if vol is None or np.isnan(vol) or vol <= 0:
            vol = 1e-6

        vols[ticker] = vol

    if not vols:
        return {"CASH": 1.0}

    raw = {ticker: float(alloc_map[ticker]) / vols[ticker] for ticker in vols}
    raw_sum = sum(raw.values())
    weights = {ticker: value / raw_sum for ticker, value in raw.items()}

    if max_weight is not None:
        weights = {ticker: min(weight, max_weight) for ticker, weight in weights.items()}
        clipped_sum = sum(weights.values())
        if clipped_sum > 0:
            weights = {ticker: weight / clipped_sum for ticker, weight in weights.items()}

    cash_weight = max(0.0, 1.0 - sum(weights.values()))
    weights["CASH"] = cash_weight

    return weights


def backtest_portfolio(
    returns_df: pd.DataFrame,
    weights: dict,
    *,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """
    Backtest a static weighted portfolio from per-period strategy returns.

    Metrics are computed from `portfolio_return`, not from `capital`.
    """
    df = returns_df.copy()
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    local_weights = dict(weights)
    for ticker in df.columns:
        local_weights.setdefault(ticker, 0.0)

    portfolio_return = np.zeros(len(df), dtype=float)
    for ticker in df.columns:
        portfolio_return += float(local_weights.get(ticker, 0.0)) * df[ticker].to_numpy()

    out = pd.DataFrame({"portfolio_return": portfolio_return}, index=df.index)
    out["capital"] = (1.0 + out["portfolio_return"]).cumprod()

    out.attrs["metrics"] = compute_performance_metrics(
        out["portfolio_return"],
        periods_per_year=periods_per_year,
        enforce_returns_input=True,
    )
    out.attrs["weights"] = local_weights

    return out