import pandas as pd

def generate_features(df: pd.DataFrame, target_horizon: int = 5) -> pd.DataFrame:
    """
    Генерирует признаки и целевую переменную для прогнозирования цен
    """
    df = df.copy()
    df.set_index("Date", inplace=True)

    # Доходности
    df["return_1d"] = df["Close"].pct_change(1)
    df["return_5d"] = df["Close"].pct_change(5)
    df["return_20d"] = df["Close"].pct_change(20)

    # Скользящие средние
    df["SMA_5"] = df["Close"].rolling(window=5).mean()
    df["SMA_20"] = df["Close"].rolling(window=20).mean()
    df["SMA_50"] = df["Close"].rolling(window=50).mean()

    # Волатильность
    df["volatility_5d"] = df["Close"].rolling(window=5).std()
    df["volatility_20d"] = df["Close"].rolling(window=20).std()

    # Лаги
    df["lag_1"] = df["Close"].shift(1)
    df["lag_5"] = df["Close"].shift(5)
    df["lag_20"] = df["Close"].shift(20)

    # Целевая переменная — доходность через N дней
    df[f"target_return_{target_horizon}d"] = df["Close"].shift(-target_horizon) / df["Close"] - 1

    # Удаляем строки с пропущенными значениями
    df.dropna(inplace=True)

    return df.reset_index()
