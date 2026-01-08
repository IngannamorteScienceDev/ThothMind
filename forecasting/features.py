import pandas as pd
import numpy as np

def generate_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values("Date")

    # === Доходности ===
    df["return_1d"] = df["Close"].pct_change(1)
    df["return_5d"] = df["Close"].pct_change(5)
    df["return_20d"] = df["Close"].pct_change(20)

    # === Скользящие средние (нормированные) ===
    df["SMA_5"] = df["Close"].rolling(5).mean() / df["Close"]
    df["SMA_20"] = df["Close"].rolling(20).mean() / df["Close"]
    df["SMA_50"] = df["Close"].rolling(50).mean() / df["Close"]

    # === Волатильность (в доходностях) ===
    df["volatility_5d"] = df["return_1d"].rolling(5).std()
    df["volatility_20d"] = df["return_1d"].rolling(20).std()

    # === Лаги доходностей (ВАЖНО) ===
    df["lag_1"] = df["return_1d"].shift(1)
    df["lag_5"] = df["return_1d"].shift(5)
    df["lag_20"] = df["return_1d"].shift(20)

    # === ЦЕЛЕВАЯ ПЕРЕМЕННАЯ (РЕГРЕССИЯ) ===
    df["target_return_5d"] = df["Close"].shift(-5) / df["Close"] - 1

    # === Очистка ===
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna().reset_index(drop=True)

    return df
