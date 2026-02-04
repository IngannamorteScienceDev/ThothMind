from __future__ import annotations

import numpy as np


def conformal_qhat(abs_residuals: np.ndarray, alpha: float) -> float:
    """
    Split conformal for regression:
      qhat = quantile_{1-alpha}(|y - yhat|) with finite-sample correction.

    We use a conservative quantile index:
      q = ceil((n+1)*(1-alpha))/n
    """
    r = np.asarray(abs_residuals, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return 0.0

    n = r.size
    k = int(np.ceil((n + 1) * (1.0 - float(alpha))))
    k = min(max(k, 1), n)  # clamp to [1, n]
    q = float(np.partition(r, k - 1)[k - 1])
    return q


def conformal_interval(y_pred: np.ndarray, qhat: float) -> tuple[np.ndarray, np.ndarray]:
    y_pred = np.asarray(y_pred, dtype=float)
    qhat = float(qhat)
    lo = y_pred - qhat
    hi = y_pred + qhat
    return lo, hi
