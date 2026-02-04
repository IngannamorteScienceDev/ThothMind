from __future__ import annotations

import pandas as pd


class SMATrendPolicy:
    """
    Baseline policy:
    - if close > SMA(window): target_exposure = 1.0
    - else: target_exposure = 0.0

    IMPORTANT: The signal is computed on day t and applied on day t+1 in simulator.
    """

    def __init__(self, sma_window: int = 200):
        self.sma_window = int(sma_window)

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df[["date", "ticker", "close"]].copy()
        sma = df["close"].rolling(self.sma_window).mean()
        out["target_exposure"] = (df["close"] > sma).astype(float)
        out["signal_name"] = f"sma_{self.sma_window}"
        return out
