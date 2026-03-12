from __future__ import annotations

import numpy as np
import pandas as pd


def sanity_buyhold_matches_theory(sim_df: pd.DataFrame, tol: float = 1e-10) -> dict:
    """
    If costs are zero and policy is buy&hold, equity should match:
    equity[t] = cumprod(1 + ret_1d[t]) with initial 1.0 (from the first usable row).

    Note: our simulator builds equity iteratively; this checks consistency.
    """
    r = sim_df["ret_1d"].astype(float).to_numpy()
    pnl = sim_df["pnl"].astype(float).to_numpy()
    costs = sim_df["total_cost"].astype(float).to_numpy()

    # If costs are not ~0, sanity doesn't apply strictly
    costs_ok = bool(np.all(np.abs(costs) < 1e-12))

    # Theoretical if position_prev = 1 always:
    # pnl_theory = ret_1d
    pnl_theory = r.copy()

    # Compare pnl (approx) with pnl_theory where both are finite
    m = np.isfinite(pnl) & np.isfinite(pnl_theory)
    diff = float(np.max(np.abs(pnl[m] - pnl_theory[m]))) if np.any(m) else 0.0

    ok = (diff <= tol) if costs_ok else True  # if costs present, we don't fail hard

    return {
        "check": "buyhold_matches_ret_1d_when_costs_zero",
        "costs_all_zero": costs_ok,
        "max_abs_pnl_diff": diff,
        "passed": bool(ok),
    }


def sanity_flat_has_no_pnl(sim_df: pd.DataFrame, tol: float = 1e-10) -> dict:
    """
    Flat policy should have pnl ~ -costs (but turnover should be ~0),
    so pnl should be ~0 and equity should be ~constant.
    """
    pnl = sim_df["pnl"].astype(float).to_numpy()
    max_abs_pnl = float(np.max(np.abs(pnl[np.isfinite(pnl)]))) if len(pnl) else 0.0
    return {
        "check": "flat_policy_pnl_near_zero",
        "max_abs_pnl": max_abs_pnl,
        "passed": bool(max_abs_pnl <= tol),
    }
