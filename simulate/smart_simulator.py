import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def simulate_with_filters(df: pd.DataFrame, y_proba: np.ndarray, threshold: float):
    df = df.copy()
    df = df.iloc[-len(y_proba):]  # test period
    df["proba"] = y_proba
    df["signal"] = (df["proba"] > threshold).astype(int)

    # 📊 Добавим фильтр по тренду: бычий рынок
    df["filter"] = (df["SMA_20"] > df["SMA_50"]) & (df["SMA_5"] > df["SMA_20"])
    df["final_signal"] = df["signal"] & df["filter"]

    # 🎲 Случайная стратегия (для сравнения)
    np.random.seed(42)
    df["random_signal"] = np.random.randint(0, 2, size=len(df))

    # 📈 Расчёт доходностей
    df["return"] = df["target_return_5d"]
    df["strategy_return"] = df["final_signal"] * df["return"]
    df["random_return"] = df["random_signal"] * df["return"]

    # 💰 Кумулятивный рост капитала
    df["capital"] = (1 + df["strategy_return"]).cumprod()
    df["buy_and_hold"] = (1 + df["return"]).cumprod()
    df["random_capital"] = (1 + df["random_return"]).cumprod()

    return df
