import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def simulate_strategy(df: pd.DataFrame, y_pred: np.ndarray, threshold: float = 0.01):
    """
    Симулирует стратегию: покупаем, если предсказание > threshold
    """
    df = df.copy()
    df = df.iloc[-len(y_pred):]  # оставим только test-период
    df["predicted_return"] = y_pred
    df["actual_return"] = df["target_return_5d"]
    df["signal"] = (df["predicted_return"] > threshold).astype(int)
    df["strategy_return"] = df["signal"] * df["actual_return"]

    # Equity curve
    df["capital"] = (1 + df["strategy_return"]).cumprod()

    # Бенчмарк (если бы просто держали)
    df["buy_and_hold"] = (1 + df["actual_return"]).cumprod()

    return df
