from __future__ import annotations

import numpy as np
import pandas as pd


class BasePolicy:
    name: str = "base"

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError


class BuyHoldPolicy(BasePolicy):
    """
    target_exposure = 1.0 always
    """
    name = "buyhold"

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df[["date", "ticker", "close"]].copy()
        out["target_exposure"] = 1.0
        out["signal_name"] = self.name
        return out


class FlatPolicy(BasePolicy):
    """
    target_exposure = 0.0 always (cash)
    """
    name = "flat"

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df[["date", "ticker", "close"]].copy()
        out["target_exposure"] = 0.0
        out["signal_name"] = self.name
        return out


class SMATrendPolicy(BasePolicy):
    """
    Baseline trend policy:
    - if close > SMA(window): target_exposure = 1.0
    - else: target_exposure = 0.0

    IMPORTANT: Signal computed on day t and applied on day t+1 in simulator.
    """
    name = "sma_trend"

    def __init__(self, sma_window: int = 200):
        self.sma_window = int(sma_window)

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df[["date", "ticker", "close"]].copy()
        sma = df["close"].rolling(self.sma_window).mean()
        out["target_exposure"] = (df["close"] > sma).astype(float)
        out["signal_name"] = f"sma_{self.sma_window}"
        return out


class RandomPolicy(BasePolicy):
    """
    Seeded random baseline:
    - target_exposure is 1.0 with probability p_long else 0.0
    """
    name = "random"

    def __init__(self, seed: int = 42, p_long: float = 0.5):
        self.seed = int(seed)
        self.p_long = float(p_long)

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed)
        out = df[["date", "ticker", "close"]].copy()
        out["target_exposure"] = (rng.random(len(df)) < self.p_long).astype(float)
        out["signal_name"] = f"random_p{self.p_long:.2f}_s{self.seed}"
        return out
