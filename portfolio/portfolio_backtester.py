import numpy as np
import pandas as pd

from metrics.performance import compute_performance_metrics


def compute_inverse_vol_weights(
    returns_df: pd.DataFrame,
    alloc_map: dict,
    vol_lookback: int = 20,
    max_weight: float = 0.5
) -> dict:
    """
    returns_df: columns = tickers, rows = time, values = per-period returns
    alloc_map: {ticker: allocation in {0, 0.5, 1.0}}
    """

    vols = {}
    for t in returns_df.columns:
        if alloc_map.get(t, 0.0) <= 0:
            continue
        vol = returns_df[t].rolling(vol_lookback).std().iloc[-1]
        if vol is None or np.isnan(vol) or vol == 0:
            vol = 1e-6
        vols[t] = vol

    if not vols:
        return {"CASH": 1.0}

    raw = {t: (alloc_map[t] / vols[t]) for t in vols.keys()}
    s = sum(raw.values())
    weights = {t: v / s for t, v in raw.items()}

    # cap weights
    if max_weight is not None:
        weights = {t: min(w, max_weight) for t, w in weights.items()}
        s2 = sum(weights.values())
        if s2 > 0:
            weights = {t: w / s2 for t, w in weights.items()}

    cash = max(0.0, 1.0 - sum(weights.values()))
    weights["CASH"] = cash
    return weights


def backtest_portfolio(
    returns_df: pd.DataFrame,
    weights: dict
) -> pd.DataFrame:
    """
    returns_df: columns = tickers, must match weights keys (except CASH),
               values = strategy returns per period
    weights: dict {ticker: weight, CASH: weight}
    """

    df = returns_df.copy()
    for t in df.columns:
        if t not in weights:
            weights[t] = 0.0

    # portfolio return = sum_i w_i * r_i  (cash return = 0)
    port_ret = np.zeros(len(df))
    for t in df.columns:
        port_ret += weights.get(t, 0.0) * df[t].values

    out = pd.DataFrame({
        "portfolio_return": port_ret,
    }, index=df.index)

    out["capital"] = (1.0 + out["portfolio_return"]).cumprod()

    # metrics
    m = compute_performance_metrics(out["capital"])
    out.attrs["metrics"] = m
    out.attrs["weights"] = weights

    return out
