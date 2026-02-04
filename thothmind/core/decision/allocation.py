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
