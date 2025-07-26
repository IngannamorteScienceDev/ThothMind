import pandas as pd
import os
import glob

def load_ticker_data(ticker: str, base_path: str = "data") -> pd.DataFrame:
    """
    Загружает данные по тикеру из папок Stocks или ETFs.
    Преобразует колонку 'Date' в datetime и добавляет колонку 'ticker'.
    """
    ticker = ticker.lower()
    paths = [
        os.path.join(base_path, "Stocks", f"{ticker}.us.txt"),
        os.path.join(base_path, "ETFs", f"{ticker}.us.txt")
    ]
    for path in paths:
        if os.path.exists(path):
            df = pd.read_csv(path)
            df["ticker"] = ticker.upper()
            df["Date"] = pd.to_datetime(df["Date"])
            return df
    raise FileNotFoundError(f"{ticker} не найден в Stocks/ или ETFs/")

def get_available_tickers(base_path: str = "data") -> list:
    """
    Возвращает список всех доступных тикеров в директориях Stocks и ETFs.
    """
    files = glob.glob(os.path.join(base_path, "*", "*.us.txt"))
    return sorted(set(os.path.basename(f).replace(".us.txt", "").upper() for f in files))

def describe_ticker(df: pd.DataFrame) -> pd.DataFrame:
    """
    Возвращает базовую описательную статистику по числовым колонкам тикера.
    """
    return df.describe()

def check_missing_values(df: pd.DataFrame) -> pd.Series:
    """
    Проверяет наличие пропущенных значений в DataFrame.
    """
    return df.isna().sum()
