from __future__ import annotations

import pandas as pd

from data.smart_loader import load_ticker_data


def load_ohlcv(
    ticker: str,
    base_path: str = "data",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """
    Load OHLCV data using legacy loader and normalize columns to:
    date, open, high, low, close, volume, ticker
    """
    df = load_ticker_data(ticker, base_path=base_path).copy()

    # Legacy columns are usually: Date, Open, High, Low, Close, Volume
    rename_map = {
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    df = df.rename(columns=rename_map)

    # Basic validation / normalization
    if "date" not in df.columns:
        raise ValueError("Expected 'Date' column in raw data (after rename: 'date').")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Filter dates if requested
    if start is not None:
        df = df[df["date"] >= pd.to_datetime(start)]
    if end is not None:
        df = df[df["date"] <= pd.to_datetime(end)]

    required = ["date", "open", "high", "low", "close", "volume", "ticker"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns after normalization: {missing}")

    return df[required].reset_index(drop=True)
