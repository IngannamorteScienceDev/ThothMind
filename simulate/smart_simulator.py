from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from simulate.simulator import simulate_strategy


def simulate_with_allocation(
    df: pd.DataFrame,
    predictions: np.ndarray,
    allocation: float,
    entry_threshold: float = 0.01,
    commission: float = 0.001,
    *,
    horizon: Optional[int] = None,
    execution_lag: int = 1,
    allow_overlap: bool = False,
    daily_return_col: Optional[str] = None,
    target_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    Allocation-aware wrapper around the core simulator.

    Backward compatibility:
    - keeps columns expected by old scripts: prediction, signal, return
    - delegates the honest PnL logic to simulate.simulator.simulate_strategy()

    Notes
    -----
    Old code used target_return_5d directly as if it were a per-bar return,
    which can massively overstate performance. This wrapper now uses
    per-bar returns and a real holding schedule.
    """
    out = simulate_strategy(
        df=df,
        y_pred=predictions,
        threshold=entry_threshold,
        horizon=horizon,
        execution_lag=execution_lag,
        allocation=allocation,
        commission=commission,
        allow_overlap=allow_overlap,
        daily_return_col=daily_return_col,
        target_col=target_col,
    )

    out["prediction"] = out["predicted_return"]

    return out