from __future__ import annotations

import numpy as np
import pandas as pd

from thothmind.core.stats.bootstrap import moving_block_bootstrap_stats


def _clean_positive_equity(eq: np.ndarray) -> np.ndarray:
    eq = np.asarray(eq, dtype=float)
    m = np.isfinite(eq) & (eq > 0.0)
    out = np.full_like(eq, np.nan, dtype=float)
    out[m] = eq[m]
    return out


def bootstrap_oos_outperformance(
    sim_strategy: pd.DataFrame,
    sim_buyhold: pd.DataFrame,
    n_boot: int = 5000,
    block_len: int = 20,
    ci_alpha: float = 0.05,
    seed: int = 42,
) -> tuple[dict, pd.DataFrame]:
    """
    Bootstrap significance of OOS outperformance using EQUITY (robust, unit-free).

    We align by date and compute daily log-returns from equity:
      r_t = log(eq_t) - log(eq_{t-1})
    diff_t = r_strat_t - r_bh_t

    Statistic: sum(diff_t) => log relative performance over OOS horizon.
    """
    df_s = sim_strategy[["date", "equity"]].copy()
    df_b = sim_buyhold[["date", "equity"]].copy()

    df_s["date"] = pd.to_datetime(df_s["date"])
    df_b["date"] = pd.to_datetime(df_b["date"])

    merged = pd.merge(df_s, df_b, on="date", how="inner", suffixes=("_strat", "_bh")).sort_values("date")
    if len(merged) < 60:
        raise ValueError(f"Too few aligned OOS days for bootstrap: {len(merged)}")

    eq_s = _clean_positive_equity(merged["equity_strat"].to_numpy())
    eq_b = _clean_positive_equity(merged["equity_bh"].to_numpy())

    # Drop rows where either equity is invalid
    mask = np.isfinite(eq_s) & np.isfinite(eq_b)
    eq_s = eq_s[mask]
    eq_b = eq_b[mask]

    if len(eq_s) < 60:
        raise ValueError(f"Too few valid equity points after cleaning: {len(eq_s)}")

    log_s = np.log(eq_s)
    log_b = np.log(eq_b)

    # daily log returns
    r_s = np.diff(log_s)
    r_b = np.diff(log_b)
    diff = r_s - r_b

    if len(diff) < 50:
        raise ValueError(f"Too few diff points for bootstrap: {len(diff)}")

    actual_log_rel = float(np.sum(diff))
    actual_rel_return = float(np.exp(actual_log_rel) - 1.0)
    actual_mean_log_diff = float(np.mean(diff))

    boot_log_rel = moving_block_bootstrap_stats(
        diff,
        stat_fn=lambda x: float(np.sum(x)),
        n_boot=int(n_boot),
        block_len=int(block_len),
        seed=int(seed),
    )

    boot_rel_return = np.exp(boot_log_rel) - 1.0

    p_one_sided = float((1.0 + np.sum(boot_log_rel <= 0.0)) / (len(boot_log_rel) + 1.0))

    lo_q = float(np.quantile(boot_log_rel, ci_alpha / 2))
    hi_q = float(np.quantile(boot_log_rel, 1.0 - ci_alpha / 2))
    ci_lo_rel = float(np.exp(lo_q) - 1.0)
    ci_hi_rel = float(np.exp(hi_q) - 1.0)

    prob_outperform = float(np.mean(boot_log_rel > 0.0))

    summary = {
        "n_days_aligned": int(len(diff)),
        "n_boot": int(n_boot),
        "block_len": int(block_len),
        "ci_alpha": float(ci_alpha),
        "actual_log_rel": actual_log_rel,
        "actual_rel_return": actual_rel_return,
        "actual_mean_log_diff": actual_mean_log_diff,
        "p_value_one_sided": p_one_sided,
        "ci_rel_return_low": ci_lo_rel,
        "ci_rel_return_high": ci_hi_rel,
        "prob_outperform": prob_outperform,
        "interpretation": (
            "Relative outperformance computed from equity log-returns. "
            "p_value_one_sided tests H1: outperformance > 0 using moving-block bootstrap."
        ),
    }

    boot_df = pd.DataFrame(
        {
            "boot_log_rel": boot_log_rel,
            "boot_rel_return": boot_rel_return,
        }
    )

    return summary, boot_df
