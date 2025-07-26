import pandas as pd

def generate_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values("Date")

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

    # Целевая переменная: доходность через 5 дней
    df["target_return_5d"] = df["Close"].shift(-5) / df["Close"] - 1

    # Бинарная цель: вырастет ли цена
    df["target_up_5d"] = (df["target_return_5d"] > 0).astype(int)

    # Удалим строки с пропущенными значениями
    df = df.dropna().reset_index(drop=True)

    return df
