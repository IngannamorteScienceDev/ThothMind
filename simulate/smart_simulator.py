import pandas as pd
import numpy as np


def simulate_with_allocation(
    df: pd.DataFrame,
    predictions: np.ndarray,
    allocation: float,
    entry_threshold: float = 0.01,
    commission: float = 0.001
):
    """
    Simulation with capital allocation (0 / 0.5 / 1.0).
    """

    df = df.copy()
    df = df.iloc[-len(predictions):]

    df["prediction"] = predictions
    df["signal"] = (df["prediction"] > entry_threshold).astype(int)

    # Apply allocation
    df["position"] = df["signal"] * allocation

    df["return"] = df["target_return_5d"]
    df["strategy_return"] = df["position"] * df["return"] - commission * df["position"]

    df["capital"] = (1 + df["strategy_return"]).cumprod()
    df["buy_and_hold"] = (1 + df["return"]).cumprod()

    return df
