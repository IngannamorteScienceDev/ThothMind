from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BootstrapConfig:
    n_boot: int = 2000
    block_len: int = 20
    ci_alpha: float = 0.05
    seed: int = 42
    show_progress: bool = True


def _as_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _validate_sim(sim: pd.DataFrame, name: str) -> None:
    if sim is None or len(sim) == 0:
        raise ValueError(f"{name} is empty")
    for col in ["date", "equity"]:
        if col not in sim.columns:
            raise KeyError(f"{name} must contain '{col}' column")


def _align_equity(sim_a: pd.DataFrame, sim_b: pd.DataFrame) -> pd.DataFrame:
    """
    Align two sims on date and keep only common dates.
    """
    a = sim_a[["date", "equity"]].copy()
    b = sim_b[["date", "equity"]].copy()

    a["date"] = _as_dt(a["date"])
    b["date"] = _as_dt(b["date"])

    a["equity"] = pd.to_numeric(a["equity"], errors="coerce")
    b["equity"] = pd.to_numeric(b["equity"], errors="coerce")

    a = a.dropna(subset=["date", "equity"]).sort_values("date")
    b = b.dropna(subset=["date", "equity"]).sort_values("date")

    m = a.merge(b, on="date", how="inner", suffixes=("_a", "_b"))
    if len(m) < 10:
        raise ValueError(f"Not enough aligned rows after merge: {len(m)}")

    # guard: equity must be positive
    m["equity_a"] = m["equity_a"].clip(lower=1e-12)
    m["equity_b"] = m["equity_b"].clip(lower=1e-12)
    return m


def _moving_block_indices(n: int, block_len: int, rng: np.random.Generator) -> np.ndarray:
    """
    Generate indices of length n by sampling moving blocks of length block_len.
    """
    if block_len <= 1:
        return rng.integers(0, n, size=n)

    out = np.empty(n, dtype=int)
    pos = 0
    max_start = max(0, n - block_len)

    while pos < n:
        start = int(rng.integers(0, max_start + 1))
        blk = np.arange(start, start + block_len, dtype=int)
        take = min(block_len, n - pos)
        out[pos : pos + take] = blk[:take]
        pos += take

    return out


def _iter_range(n: int, desc: str, show_progress: bool):
    """
    Iteration helper with Rich progress (fallbacks silently if Rich not installed).
    """
    if not show_progress:
        return range(n)

    try:
        from rich.progress import track

        return track(range(n), description=desc, transient=True)
    except Exception:
        return range(n)


def bootstrap_oos_outperformance(
    sim_strategy: pd.DataFrame,
    sim_buyhold: pd.DataFrame,
    n_boot: int = 2000,
    block_len: int = 20,
    ci_alpha: float = 0.05,
    seed: int = 42,
    show_progress: bool = True,
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Moving-block bootstrap for OOS outperformance (strategy vs buy&hold).

    We work on aligned daily log-returns of equity:
      log_ret = log(equity_t / equity_{t-1})

    Define:
      diff_t = log_ret_strategy_t - log_ret_buyhold_t
      actual_log_rel = sum(diff_t)
      actual_rel_return = exp(actual_log_rel) - 1

    Bootstrap:
      - sample diff_t with moving blocks
      - compute boot_log_rel and boot_rel_return

    Outputs:
      sig_summary: dict with keys:
        n_days_aligned, n_boot, block_len, ci_alpha,
        actual_log_rel, actual_rel_return, actual_mean_log_diff,
        p_value_one_sided, ci_rel_return_low, ci_rel_return_high,
        prob_outperform, interpretation
      boot_df: DataFrame with columns:
        boot_log_rel, boot_rel_return
    """
    _validate_sim(sim_strategy, "sim_strategy")
    _validate_sim(sim_buyhold, "sim_buyhold")

    n_boot = int(n_boot)
    block_len = int(block_len)
    ci_alpha = float(ci_alpha)
    seed = int(seed)

    if n_boot <= 0:
        raise ValueError("n_boot must be > 0")
    if block_len <= 0:
        raise ValueError("block_len must be > 0")
    if not (0.0 < ci_alpha < 1.0):
        raise ValueError("ci_alpha must be in (0,1)")

    aligned = _align_equity(sim_strategy, sim_buyhold)
    eq_s = aligned["equity_a"].to_numpy(dtype=float)
    eq_b = aligned["equity_b"].to_numpy(dtype=float)

    # daily log returns
    log_s = np.log(eq_s)
    log_b = np.log(eq_b)

    log_ret_s = np.diff(log_s)  # length n-1
    log_ret_b = np.diff(log_b)

    diff = log_ret_s - log_ret_b
    n = diff.size
    if n < max(30, block_len):
        raise ValueError(f"Not enough days for bootstrap: n_days={n}, block_len={block_len}")

    actual_log_rel = float(diff.sum())
    actual_rel_return = float(np.expm1(actual_log_rel))
    actual_mean_log_diff = float(diff.mean())

    rng = np.random.default_rng(seed)

    boot_log_rel = np.empty(n_boot, dtype=float)
    boot_rel_return = np.empty(n_boot, dtype=float)

    for i in _iter_range(n_boot, desc="bootstrap OOS outperformance", show_progress=show_progress):
        idx = _moving_block_indices(n=n, block_len=block_len, rng=rng)
        s = float(diff[idx].sum())
        boot_log_rel[i] = s
        boot_rel_return[i] = float(np.expm1(s))

    boot_df = pd.DataFrame(
        {
            "boot_log_rel": boot_log_rel,
            "boot_rel_return": boot_rel_return,
        }
    )

    # Probability of outperforming > 0
    prob_outperform = float((boot_rel_return > 0.0).mean())

    # One-sided p-value for H1: outperformance > 0
    # (consistent with earlier runs: p ≈ 1 - prob_outperform)
    p_value_one_sided = float(1.0 - prob_outperform)

    lo_q = float(np.quantile(boot_rel_return, ci_alpha / 2.0))
    hi_q = float(np.quantile(boot_rel_return, 1.0 - ci_alpha / 2.0))

    sig_summary: Dict[str, Any] = {
        "n_days_aligned": int(n),
        "n_boot": int(n_boot),
        "block_len": int(block_len),
        "ci_alpha": float(ci_alpha),
        "actual_log_rel": actual_log_rel,
        "actual_rel_return": actual_rel_return,
        "actual_mean_log_diff": actual_mean_log_diff,
        "p_value_one_sided": p_value_one_sided,
        "ci_rel_return_low": lo_q,
        "ci_rel_return_high": hi_q,
        "prob_outperform": prob_outperform,
        "interpretation": (
            "Relative outperformance computed from equity log-returns. "
            "p_value_one_sided tests H1: outperformance > 0 using moving-block bootstrap."
        ),
    }

    return sig_summary, boot_df