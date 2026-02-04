from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from xgboost import XGBRegressor


@dataclass
class XGBConfig:
    n_estimators: int = 600
    max_depth: int = 4
    learning_rate: float = 0.03
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_lambda: float = 1.0
    min_child_weight: float = 1.0
    random_state: int = 42


class XGBReturnRegressor:
    """
    Simple, strong baseline ML model for return regression.
    We keep it minimal now; later we can add:
    - regime-aware models
    - calibrations
    - conformal intervals
    """

    def __init__(self, cfg: XGBConfig):
        self.cfg = cfg
        self.model = XGBRegressor(
            n_estimators=cfg.n_estimators,
            max_depth=cfg.max_depth,
            learning_rate=cfg.learning_rate,
            subsample=cfg.subsample,
            colsample_bytree=cfg.colsample_bytree,
            reg_lambda=cfg.reg_lambda,
            min_child_weight=cfg.min_child_weight,
            random_state=cfg.random_state,
            n_jobs=-1,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        self.model.fit(X, y)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict(X)
