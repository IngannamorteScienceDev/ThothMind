import pandas as pd
import numpy as np

def simulate_with_filters(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    threshold: float,
    use_filters: bool = True,
    commission: float = 0.001
):
    df = df.copy()
    df = df.iloc[-len(y_pred):]

    # Предсказанная доходность
    df["predicted_return"] = y_pred

    # Сигнал входа
    df["signal"] = (df["predicted_return"] > threshold).astype(int)

    # Технический фильтр тренда
    if use_filters:
        df["filter"] = (
            (df["SMA_20"] > df["SMA_50"]) &
            (df["SMA_5"] > df["SMA_20"])
        )
        df["final_signal"] = df["signal"] & df["filter"]
    else:
        df["final_signal"] = df["signal"]

    # === РЕАЛЬНАЯ ДОХОДНОСТЬ ===
    # Вход сегодня → выход завтра (без заглядывания в будущее)
    df["market_return"] = df["return_1d"].shift(-1)

    # Комиссия только при входе
    df["strategy_return"] = (
        df["final_signal"] * df["market_return"]
        - df["final_signal"] * commission
    )

    # Buy & Hold
    df["buy_and_hold"] = (1 + df["market_return"]).cumprod()

    # Стратегия
    df["capital"] = (1 + df["strategy_return"]).cumprod()

    # Random baseline
    np.random.seed(42)
    df["random_signal"] = np.random.randint(0, 2, size=len(df))
    df["random_return"] = df["random_signal"] * df["market_return"]
    df["random_capital"] = (1 + df["random_return"]).cumprod()

    return df
