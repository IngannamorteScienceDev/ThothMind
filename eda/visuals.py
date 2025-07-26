import pandas as pd
import matplotlib.pyplot as plt

def plot_price_with_sma(df: pd.DataFrame, ticker: str):
    """
    Строит график цены закрытия и скользящих средних
    """
    df = df.copy()
    df.set_index("Date", inplace=True)

    # Скользящие средние
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=200).mean()

    # Создание графиков
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})

    # График цены
    ax1.plot(df.index, df["Close"], label="Close", linewidth=1.2)
    ax1.plot(df.index, df["SMA20"], label="SMA 20", linestyle="--")
    ax1.plot(df.index, df["SMA50"], label="SMA 50", linestyle="--")
    ax1.plot(df.index, df["SMA200"], label="SMA 200", linestyle="--")
    ax1.set_title(f"{ticker.upper()} — Price with SMA")
    ax1.set_ylabel("Price")
    ax1.legend()
    ax1.grid(True)

    # График объёма
    ax2.bar(df.index, df["Volume"], width=1, alpha=0.6)
    ax2.set_ylabel("Volume")
    ax2.set_xlabel("Date")
    ax2.grid(True)

    plt.tight_layout()
    plt.show()
