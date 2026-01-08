import numpy as np
import pandas as pd


def allocate_capital(returns: pd.Series, allocation: float) -> pd.Series:
    """
    Simple capital allocation layer.

    Parameters
    ----------
    returns : pd.Series
        Asset returns (e.g. 5-day forward returns).
    allocation : float
        Fraction of capital allocated to risky asset (0.0 / 0.5 / 1.0).

    Returns
    -------
    pd.Series
        Allocated returns.
    """
    if not 0.0 <= allocation <= 1.0:
        raise ValueError("Allocation must be between 0 and 1.")

    returns = returns.copy().fillna(0.0)
    allocated_returns = allocation * returns

    return allocated_returns
