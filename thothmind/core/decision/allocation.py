from __future__ import annotations

import numpy as np


def predictions_to_exposure(
    y_pred: np.ndarray,
    thr_half: float = 0.0,
    thr_full: float = 0.001,
) -> np.ndarray:
    """
    Convert predicted forward return into discrete allocation:
      - < thr_half  -> 0.0
      - >= thr_half -> 0.5
      - >= thr_full -> 1.0

    Defaults:
      thr_half = 0.0  (positive expectation => at least 50%)
      thr_full = 0.1% (>= 0.001) => 100%
    """
    y_pred = np.asarray(y_pred, dtype=float)

    exp = np.zeros_like(y_pred, dtype=float)
    exp[y_pred >= thr_half] = 0.5
    exp[y_pred >= thr_full] = 1.0
    return exp

def conformal_to_exposure(
    y_pred: np.ndarray,
    y_lo: np.ndarray,
    y_hi: np.ndarray,
) -> np.ndarray:
    """
    Uncertainty-gated discrete allocation based on conformal interval:

      if y_lo > 0 -> 1.0 (statistically positive)
      elif y_hi < 0 -> 0.0 (statistically negative)
      else:
         if y_pred > 0 -> 0.5 (weak positive, uncertain)
         else -> 0.0
    """
    y_pred = np.asarray(y_pred, dtype=float)
    y_lo = np.asarray(y_lo, dtype=float)
    y_hi = np.asarray(y_hi, dtype=float)

    exp = np.zeros_like(y_pred, dtype=float)
    exp[y_pred > 0.0] = 0.5
    exp[y_lo > 0.0] = 1.0
    exp[y_hi < 0.0] = 0.0
    return exp
