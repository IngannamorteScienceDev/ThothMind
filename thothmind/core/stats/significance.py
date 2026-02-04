from __future__ import annotations

import numpy as np
import pandas as pd

from thothmind.core.stats.bootstrap import moving_block_bootstrap_stats


def _safe_log1p(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    # daily pnl should never be <= -1, but protect anyway
    m = np.isfinite(a) & ((1.0 + a) > 0.0)
    out = np.full_like(a, np.nan, dtype=float)
    out[m] = np.log1p(a[m])
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
    Compare strategy vs buy&hold on OOS series using block bootstrap.

    We bootstrap diff_t = log(1+pnl_strat) - log(1+pnl_bh).
    Statistic: sum(diff_t) over period => log relative performance.

    Returns:
      - summary dict
      - bootstrap dataframe with columns: boot_log_rel, boot_rel_return
    """
    df_s = sim_strategy[["date", "pnl"]].copy()
    df_b = sim_buyhold[["date", "pnl"]].copy()

    merged = pd.merge(df_s, df_b, on="date", how="inner", suffixes=("_strat", "_bh"))
    if len(merged) < 50:
        raise ValueError(f"Too few aligned OOS days for bootstrap: {len(merged)}")

    log_s = _safe_log1p(merged["pnl_strat"].to_numpy())
    log_b = _safe_log1p(merged["pnl_bh"].to_numpy())
    diff = log_s - log_b

    # Drop NaNs if any
    diff = diff[np.isfinite(diff)]
    n = len(diff)
    if n < 50:
        raise ValueError(f"Too few valid diff points after cleaning: {n}")

    actual_log_rel = float(np.sum(diff))
    actual_rel_return = float(np.exp(actual_log_rel) - 1.0)
    actual_mean_log_diff = float(np.mean(diff))

    # Bootstrap statistic: sum of diff (log relative)
    boot_log_rel = moving_block_bootstrap_stats(
        diff,
        stat_fn=lambda x: np.sum(x),
        n_boot=int(n_boot),
        block_len=int(block_len),
        seed=int(seed),
    )

    boot_rel_return = np.exp(boot_log_rel) - 1.0

    # One-sided p-value for outperformance (H0: log_rel <= 0)
    # Add +1 correction (common bootstrap p-value stabilization)
    p_one_sided = float((1.0 + np.sum(boot_log_rel <= 0.0)) / (len(boot_log_rel) + 1.0))

    # CI for relative return via bootstrap quantiles
    lo_q = float(np.quantile(boot_log_rel, ci_alpha / 2))
    hi_q = float(np.quantile(boot_log_rel, 1.0 - ci_alpha / 2))
    ci_lo_rel = float(np.exp(lo_q) - 1.0)
    ci_hi_rel = float(np.exp(hi_q) - 1.0)

    prob_outperform = float(np.mean(boot_log_rel > 0.0))

    summary = {
        "n_days_aligned": int(n),
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
            "Positive actual_rel_return means strategy outperformed buy&hold on OOS. "
            "p_value_one_sided tests H1: outperformance > 0 using block bootstrap."
        ),
    }

    boot_df = pd.DataFrame(
        {
            "boot_log_rel": boot_log_rel,
            "boot_rel_return": boot_rel_return,
        }
    )

    return summary, boot_df
