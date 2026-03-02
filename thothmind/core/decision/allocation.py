from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class AllocationConfig:
    """
    Long-only exposure mapping config.

    Defaults reproduce the previous behavior:
      - confident long (y_lo > 0)  -> high_exposure (1.0)
      - uncertain long (y_pred > 0) -> mid_exposure (0.5)
      - else -> low_exposure (0.0)
      - confident negative (y_hi < 0) -> low_exposure (0.0)
    """
    low_exposure: float = 0.0
    mid_exposure: float = 0.5
    high_exposure: float = 1.0

    # threshold for "uncertain long" decision using y_pred
    y_pred_thr: float = 0.0

    # optional width gate: if width > width_max -> prefer low_exposure
    width_max: Optional[float] = None

    # reduce churn: after a switch, lock exposure for N days (cooldown)
    min_hold_days: int = 0

    clip_min: float = 0.0
    clip_max: float = 1.0


def _cooldown_hold(exposure: np.ndarray, min_hold_days: int) -> np.ndarray:
    """
    Cooldown hold:
      - when exposure changes, lock the new value for `min_hold_days` subsequent days
      - prevents rapid flip-flops (reduces turnover/costs)
    """
    if min_hold_days is None or int(min_hold_days) <= 0 or len(exposure) == 0:
        return exposure

    hold = int(min_hold_days)
    out = exposure.astype(float).copy()
    last = float(out[0])
    cooldown = 0

    for i in range(1, len(out)):
        x = float(out[i])

        if cooldown > 0:
            out[i] = last
            cooldown -= 1
            continue

        if x != last:
            last = x
            out[i] = last
            cooldown = hold  # lock after switch
        else:
            out[i] = last

    return out


def conformal_to_exposure(
    *,
    y_pred: np.ndarray,
    y_lo: np.ndarray,
    y_hi: np.ndarray,
    low_exposure: float = 0.0,
    mid_exposure: float = 0.5,
    high_exposure: float = 1.0,
    y_pred_thr: float = 0.0,
    width_max: Optional[float] = None,
    min_hold_days: int = 0,
    clip_min: float = 0.0,
    clip_max: float = 1.0,
) -> np.ndarray:
    """
    Map conformal interval + point prediction to long-only exposure.

    Rules:
      1) If y_hi < 0 -> low_exposure
      2) If y_lo > 0 -> high_exposure
      3) Else (interval crosses 0):
           - if y_pred > y_pred_thr AND (width_max is None OR width <= width_max) -> mid_exposure
           - else -> low_exposure

    Then apply cooldown hold (min_hold_days).
    """
    y_pred = np.asarray(y_pred, dtype=float)
    y_lo = np.asarray(y_lo, dtype=float)
    y_hi = np.asarray(y_hi, dtype=float)

    if y_pred.shape != y_lo.shape or y_pred.shape != y_hi.shape:
        raise ValueError("y_pred, y_lo, y_hi must have the same shape")

    width = y_hi - y_lo

    low = float(low_exposure)
    mid = float(mid_exposure)
    high = float(high_exposure)

    exp = np.full_like(y_pred, fill_value=low, dtype=float)

    # confident negative -> low
    neg = y_hi < 0.0
    exp[neg] = low

    # confident positive -> high
    pos = y_lo > 0.0
    exp[pos] = high

    # uncertain: interval crosses 0
    cross = ~(neg | pos)
    if np.any(cross):
        ok_width = np.ones_like(y_pred, dtype=bool)
        if width_max is not None:
            ok_width = width <= float(width_max)

        weak_long = (y_pred > float(y_pred_thr)) & ok_width
        exp[cross & weak_long] = mid
        exp[cross & ~weak_long] = low

    # clamp + churn control
    exp = np.clip(exp, float(clip_min), float(clip_max))
    exp = _cooldown_hold(exp, int(min_hold_days))

    return exp